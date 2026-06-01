import { readdir, readFile, stat } from 'node:fs/promises'
import path from 'node:path'
import { gzipSync } from 'node:zlib'

const root = process.cwd()
const distDir = path.join(root, 'dist')
const srcDir = path.join(root, 'src')
const budgets = {
  indexHtml: 2 * 1024,
  cssGzip: 36 * 1024,
  jsGzip: 260 * 1024,
  largestJsChunkGzip: 70 * 1024,
  dashboardRouteGzip: 22 * 1024,
  watchlistReorderGzip: 5 * 1024,
}

const forbiddenPatterns = [
  /fonts\.googleapis/i,
  /fonts\.gstatic/i,
  /@import\s+url/i,
]
const forbiddenSourceImports = [
  [/from\s+['"]recharts['"]/i, 'Recharts import; use dependency-free SVG charts for small app charts'],
  [/from\s+['"]@dnd-kit\//i, 'Dnd Kit import; use native drag and keyboard reorder without shipping a DnD library'],
]

async function collectFiles(dir) {
  const entries = await readdir(dir, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      files.push(...await collectFiles(fullPath))
    } else {
      files.push(fullPath)
    }
  }
  return files
}

function formatKb(bytes) {
  return `${(bytes / 1024).toFixed(2)} kB`
}

const files = await collectFiles(distDir)
const htmlFiles = files.filter((file) => file.endsWith('.html'))
const cssFiles = files.filter((file) => file.endsWith('.css'))
const jsFiles = files.filter((file) => file.endsWith('.js'))

let failed = false
const metrics = {
  indexHtml: 0,
  cssGzip: 0,
  jsGzip: 0,
  largestJsChunkGzip: 0,
  largestJsChunk: '',
  dashboardRouteGzip: 0,
  dashboardRouteChunk: '',
  watchlistDndChunk: '',
  watchlistDndChunkGzip: 0,
}

for (const file of htmlFiles) {
  const { size } = await stat(file)
  if (path.basename(file) === 'index.html') {
    metrics.indexHtml = size
  }
}

for (const file of cssFiles) {
  const source = await readFile(file)
  metrics.cssGzip += gzipSync(source).length
}

for (const file of jsFiles) {
  const source = await readFile(file)
  const gzipSize = gzipSync(source).length
  metrics.jsGzip += gzipSize
  if (gzipSize > metrics.largestJsChunkGzip) {
    metrics.largestJsChunkGzip = gzipSize
    metrics.largestJsChunk = path.relative(distDir, file)
  }
  if (/Dashboard-.+\.js$/.test(path.basename(file))) {
    metrics.dashboardRouteGzip = gzipSize
    metrics.dashboardRouteChunk = path.relative(distDir, file)
  }
  if (/WatchlistDndList-.+\.js$/.test(path.basename(file))) {
    metrics.watchlistDndChunk = path.relative(distDir, file)
    metrics.watchlistDndChunkGzip = gzipSize
  }
}

for (const file of [...htmlFiles, ...cssFiles]) {
  const source = await readFile(file, 'utf8')
  for (const pattern of forbiddenPatterns) {
    if (pattern.test(source)) {
      failed = true
      console.error(`Forbidden performance pattern ${pattern} in ${path.relative(distDir, file)}`)
    }
  }
}

const sourceFiles = await collectFiles(srcDir)
for (const file of sourceFiles.filter((sourceFile) => /\.(tsx|ts|jsx|js)$/.test(sourceFile))) {
  const source = await readFile(file, 'utf8')
  for (const [pattern, label] of forbiddenSourceImports) {
    if (pattern.test(source)) {
      failed = true
      console.error(`Forbidden source dependency ${label} in ${path.relative(root, file)}`)
    }
  }
}

const packageJson = JSON.parse(await readFile(path.join(root, 'package.json'), 'utf8'))
const packageDependencies = {
  ...packageJson.dependencies,
  ...packageJson.devDependencies,
}
for (const dependencyName of Object.keys(packageDependencies)) {
  if (dependencyName.startsWith('@dnd-kit/')) {
    failed = true
    console.error(`Forbidden package dependency ${dependencyName}; use the native watchlist reorder implementation`)
  }
}

const checks = [
  ['index.html raw', metrics.indexHtml, budgets.indexHtml],
  ['CSS gzip total', metrics.cssGzip, budgets.cssGzip],
  ['JS gzip total', metrics.jsGzip, budgets.jsGzip],
  [`largest JS gzip (${metrics.largestJsChunk})`, metrics.largestJsChunkGzip, budgets.largestJsChunkGzip],
  [`Dashboard route gzip (${metrics.dashboardRouteChunk})`, metrics.dashboardRouteGzip, budgets.dashboardRouteGzip],
  [`watchlist reorder gzip (${metrics.watchlistDndChunk})`, metrics.watchlistDndChunkGzip, budgets.watchlistReorderGzip],
]

if (!metrics.watchlistDndChunk) {
  failed = true
  console.error('Missing lazy WatchlistDndList chunk; custom reorder code should stay outside the Dashboard route chunk')
}

for (const [label, actual, budget] of checks) {
  const ok = actual <= budget
  console.log(`${ok ? 'PASS' : 'FAIL'} ${label}: ${formatKb(actual)} / ${formatKb(budget)}`)
  if (!ok) failed = true
}

if (failed) {
  process.exitCode = 1
}
