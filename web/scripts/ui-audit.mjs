import { readdir, readFile } from 'node:fs/promises'
import path from 'node:path'

const root = process.cwd()
const srcDir = path.join(root, 'src')
const styleDir = path.join(srcDir, 'styles')
const indexPath = path.join(root, 'index.html')
const tokensPath = path.join(styleDir, 'parts', 'tokens.css')
const globalCssPath = path.join(styleDir, 'global.css')

let failed = false
const failures = []

function fail(message) {
  failed = true
  failures.push(message)
}

async function collectFiles(dir, predicate) {
  const entries = await readdir(dir, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      files.push(...await collectFiles(fullPath, predicate))
    } else if (predicate(fullPath)) {
      files.push(fullPath)
    }
  }
  return files
}

function relative(file) {
  return path.relative(root, file)
}

function lineFor(source, index) {
  return source.slice(0, index).split(/\r?\n/).length
}

function stripJsxText(body) {
  return body
    .replace(/<[^>]+>/g, '')
    .replace(/\{[^}]+\}/g, 'x')
    .replace(/\s+/g, '')
    .trim()
}

function hasAccessibleName(attrs, body) {
  return /aria-label\s*=/.test(attrs)
    || /aria-labelledby\s*=/.test(attrs)
    || /title\s*=/.test(attrs)
    || stripJsxText(body).length > 0
}

function hasTrueAriaHidden(attrs) {
  return /\baria-hidden\s*=\s*(["']true["']|\{true\})/.test(attrs)
}

function hasFalseFocusable(attrs) {
  return /\bfocusable\s*=\s*(["']false["']|\{false\})/.test(attrs)
}

async function auditJsxAccessibility() {
  const files = await collectFiles(srcDir, (file) => /\.(tsx|jsx)$/.test(file))
  let issueCount = 0

  for (const file of files) {
    const source = await readFile(file, 'utf8')

    for (const match of source.matchAll(/<button\b([\s\S]*?)>/g)) {
      const attrs = match[1] ?? ''
      if (!/\btype\s*=/.test(attrs)) {
        issueCount += 1
        fail(`${relative(file)}:${lineFor(source, match.index)} button missing type`)
      }
    }

    for (const match of source.matchAll(/<button\b([\s\S]*?)>([\s\S]*?)<\/button>/g)) {
      if (!hasAccessibleName(match[1] ?? '', match[2] ?? '')) {
        issueCount += 1
        fail(`${relative(file)}:${lineFor(source, match.index)} button missing accessible name`)
      }
    }

    for (const match of source.matchAll(/<(input|select|textarea)\b([\s\S]*?)(?:\/>|>)/g)) {
      const attrs = match[2] ?? ''
      const hasLabel = /aria-label\s*=/.test(attrs) || /aria-labelledby\s*=/.test(attrs) || /id\s*=/.test(attrs)
      if (!hasLabel) {
        issueCount += 1
        fail(`${relative(file)}:${lineFor(source, match.index)} ${match[1]} missing label hook`)
      }
    }

    for (const match of source.matchAll(/<button\b(?=[^>]*\brole\s*=\s*["']tab["'])([^>]*)>/g)) {
      const attrs = match[1] ?? ''
      if (!/\baria-controls\s*=/.test(attrs) || !/\bid\s*=/.test(attrs)) {
        issueCount += 1
        fail(`${relative(file)}:${lineFor(source, match.index)} tab button needs id and aria-controls`)
      }
      if (!/\btabIndex\s*=/.test(attrs)) {
        issueCount += 1
        fail(`${relative(file)}:${lineFor(source, match.index)} tab button needs roving tabIndex`)
      }
    }

    for (const match of source.matchAll(/<div\b(?=[^>]*\brole\s*=\s*["']tablist["'])([^>]*)>/g)) {
      const attrs = match[1] ?? ''
      const tablistEnd = source.indexOf('</div>', match.index)
      const tablistSource = tablistEnd === -1 ? '' : source.slice(match.index, tablistEnd)
      if (!/\brole\s*=\s*["']tab["']/.test(tablistSource)) {
        continue
      }
      if (!/\bonKeyDown\s*=/.test(attrs)) {
        issueCount += 1
        fail(`${relative(file)}:${lineFor(source, match.index)} tablist needs keyboard navigation handler`)
      }
    }

    for (const match of source.matchAll(/<div\b(?=[^>]*\brole\s*=\s*["']tabpanel["'])([^>]*)>/g)) {
      const attrs = match[1] ?? ''
      if (!/\baria-labelledby\s*=/.test(attrs) || !/\bid\s*=/.test(attrs)) {
        issueCount += 1
        fail(`${relative(file)}:${lineFor(source, match.index)} tabpanel needs id and aria-labelledby`)
      }
    }

    for (const match of source.matchAll(/<th\b(?=[\s\S]*?price-history-sort)([\s\S]*?)>/g)) {
      const attrs = match[1] ?? ''
      if (!/\baria-sort\s*=/.test(attrs)) {
        issueCount += 1
        fail(`${relative(file)}:${lineFor(source, match.index)} sortable table header needs aria-sort`)
      }
    }

    for (const match of source.matchAll(/<(div|span|li|tr|td|section|article)\b(?=[^>]*\bonClick\s*=)([^>]*)>/g)) {
      const attrs = match[2] ?? ''
      const hasRole = /\brole\s*=/.test(attrs)
      const hasTabIndex = /\btabIndex\s*=/.test(attrs)
      const hasKeyboardHandler = /\bonKeyDown\s*=/.test(attrs)
      if (!hasRole || !hasTabIndex || !hasKeyboardHandler) {
        issueCount += 1
        fail(`${relative(file)}:${lineFor(source, match.index)} non-native interactive ${match[1]} needs role, tabIndex, and onKeyDown`)
      }
    }
  }

  console.log(`JSX accessibility: ${issueCount === 0 ? 'PASS' : 'FAIL'} (${files.length} files, ${issueCount} issues)`)
}

async function auditSvgAccessibility() {
  const files = await collectFiles(srcDir, (file) => /\.(tsx|jsx)$/.test(file))
  let issueCount = 0

  for (const file of files) {
    const source = await readFile(file, 'utf8')

    for (const match of source.matchAll(/<svg\b([^>]*)>/g)) {
      const attrs = match[1] ?? ''
      const isHidden = hasTrueAriaHidden(attrs)
      const isNamedImage = /\brole\s*=\s*["']img["']/.test(attrs)
        && (/\baria-label\s*=/.test(attrs) || /\baria-labelledby\s*=/.test(attrs) || /\btitle\s*=/.test(attrs))

      if (isHidden) {
        if (!hasFalseFocusable(attrs)) {
          issueCount += 1
          fail(`${relative(file)}:${lineFor(source, match.index)} decorative svg needs focusable="false"`)
        }
        continue
      }

      if (!isNamedImage) {
        issueCount += 1
        fail(`${relative(file)}:${lineFor(source, match.index)} svg needs aria-hidden="true" or role="img" with an accessible name`)
      }
    }
  }

  console.log(`SVG accessibility: ${issueCount === 0 ? 'PASS' : 'FAIL'} (${issueCount} issues)`)
}

async function auditDecorativeElements() {
  const files = await collectFiles(srcDir, (file) => /\.(tsx|jsx)$/.test(file))
  const decorativeClasses = [
    'hamburger-line',
    'nav-more-caret',
    'route-transition-bar',
    'ui-empty-state-mark',
    'dashboard-accordion-arrow',
    'collapsible-chevron',
    'ap-shift-arrow',
  ]
  let issueCount = 0

  for (const file of files) {
    const source = await readFile(file, 'utf8')

    for (const match of source.matchAll(/<(span|div)\b([^>]*)>/g)) {
      const attrs = match[2] ?? ''
      const decorativeClass = decorativeClasses.find((className) => attrs.includes(className))
      if (decorativeClass && !hasTrueAriaHidden(attrs)) {
        issueCount += 1
        fail(`${relative(file)}:${lineFor(source, match.index)} ${decorativeClass} decorative element needs aria-hidden="true"`)
      }
    }
  }

  console.log(`Decorative elements: ${issueCount === 0 ? 'PASS' : 'FAIL'} (${issueCount} issues)`)
}

async function auditMenuKeyboardSupport() {
  const layoutPath = path.join(srcDir, 'components', 'Layout.tsx')
  const source = await readFile(layoutPath, 'utf8')
  const checks = [
    [/role\s*=\s*["']menu["']/, 'More menu exposes role="menu"'],
    [/role\s*=\s*["']menuitem["']/, 'More menu items expose role="menuitem"'],
    [/\baria-haspopup\s*=\s*["']menu["']/, 'More menu trigger declares aria-haspopup="menu"'],
    [/\bonKeyDown\s*=\s*\{handleMoreTriggerKeyDown\}/, 'More menu trigger handles keyboard open'],
    [/\bonKeyDown\s*=\s*\{handleMoreMenuKeyDown\}/, 'More menu handles roving keyboard navigation'],
    [/['"]ArrowDown['"]/, 'More menu supports ArrowDown'],
    [/['"]ArrowUp['"]/, 'More menu supports ArrowUp'],
    [/['"]Home['"]/, 'More menu supports Home'],
    [/['"]End['"]/, 'More menu supports End'],
    [/['"]Escape['"]/, 'More menu supports Escape close'],
  ]
  let issueCount = 0

  for (const [pattern, label] of checks) {
    if (!pattern.test(source)) {
      issueCount += 1
      fail(`${relative(layoutPath)} missing ${label}`)
    }
  }

  console.log(`Menu keyboard support: ${issueCount === 0 ? 'PASS' : 'FAIL'} (${checks.length - issueCount}/${checks.length} checks)`)
}

async function auditFocusVisible() {
  const basePath = path.join(styleDir, 'parts', 'base.css')
  const tokenSource = await readFile(tokensPath, 'utf8')
  const baseSource = await readFile(basePath, 'utf8')
  const checks = [
    [tokensPath, /--focus-ring:\s*[^;]+;/, 'focus ring token'],
    [basePath, /:focus-visible\s*\{[\s\S]*?box-shadow:\s*var\(--focus-ring\);[\s\S]*?\}/, 'global :focus-visible ring'],
    [basePath, /button:focus-visible,[\s\S]*?\[tabindex\]:focus-visible\s*\{[\s\S]*?box-shadow:\s*var\(--focus-ring\);[\s\S]*?\}/, 'interactive controls use visible focus ring'],
  ]
  let issueCount = 0

  for (const [file, pattern, label] of checks) {
    const source = file === tokensPath ? tokenSource : baseSource
    if (!pattern.test(source)) {
      issueCount += 1
      fail(`${relative(file)} missing ${label}`)
    }
  }

  console.log(`Focus-visible states: ${issueCount === 0 ? 'PASS' : 'FAIL'} (${checks.length - issueCount}/${checks.length} checks)`)
}

async function auditForbiddenSourcePatterns() {
  const files = [
    indexPath,
    ...await collectFiles(srcDir, (file) => /\.(css|ts|tsx|js|jsx)$/.test(file)),
  ]
  const forbidden = [
    [/fonts\.googleapis/i, 'Google Fonts stylesheet request'],
    [/fonts\.gstatic/i, 'Google Fonts preconnect request'],
    [/@import\s+url/i, 'render-blocking CSS url import'],
    [/background-attachment:\s*fixed/i, 'fixed background attachment'],
    [/letter-spacing:\s*-/i, 'negative letter spacing'],
    [/No data available/, 'generic English empty-state placeholder'],
  ]
  let issueCount = 0

  for (const file of files) {
    const source = await readFile(file, 'utf8')
    for (const [pattern, label] of forbidden) {
      if (pattern.test(source)) {
        issueCount += 1
        fail(`${relative(file)} contains ${label}`)
      }
    }
  }

  console.log(`Forbidden UI patterns: ${issueCount === 0 ? 'PASS' : 'FAIL'} (${issueCount} issues)`)
}

async function auditDarkModeBrowserChrome() {
  const indexSource = await readFile(indexPath, 'utf8')
  const tokenSource = await readFile(tokensPath, 'utf8')
  let issueCount = 0

  if (!/color-scheme:\s*light\s+dark\s*;/.test(tokenSource)) {
    issueCount += 1
    fail(`${relative(tokensPath)} missing color-scheme: light dark`)
  }
  if (!/<meta\s+name="theme-color"\s+media="\(\s*prefers-color-scheme:\s*light\s*\)"\s+content="#[0-9a-fA-F]{6}"\s*\/>/.test(indexSource)) {
    issueCount += 1
    fail(`${relative(indexPath)} missing light theme-color meta`)
  }
  if (!/<meta\s+name="theme-color"\s+media="\(\s*prefers-color-scheme:\s*dark\s*\)"\s+content="#[0-9a-fA-F]{6}"\s*\/>/.test(indexSource)) {
    issueCount += 1
    fail(`${relative(indexPath)} missing dark theme-color meta`)
  }

  console.log(`Dark-mode browser chrome: ${issueCount === 0 ? 'PASS' : 'FAIL'} (${3 - issueCount}/3 checks)`)
}

function parseVars(block) {
  const vars = {}
  for (const [, key, value] of block.matchAll(/--([\w-]+):\s*([^;]+);/g)) {
    vars[key] = value.trim()
  }
  return vars
}

function resolveVar(vars, value, depth = 0) {
  if (!value) throw new Error('Missing token value')
  const reference = value.match(/^var\(--([\w-]+)\)$/)
  if (!reference) return value
  if (depth > 10) throw new Error(`Circular token reference for ${value}`)
  return resolveVar(vars, vars[reference[1]], depth + 1)
}

function rgb(hex) {
  const match = hex.trim().match(/^#([0-9a-f]{6})$/i)
  if (!match) throw new Error(`Unsupported color ${hex}`)
  const n = Number.parseInt(match[1], 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

function luminance(hex) {
  return rgb(hex)
    .map((channel) => {
      const v = channel / 255
      return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
    })
    .reduce((sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index], 0)
}

function contrast(a, b) {
  const [l1, l2] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (l1 + 0.05) / (l2 + 0.05)
}

async function auditTokenContrast() {
  const source = await readFile(tokensPath, 'utf8')
  const rootMatch = source.match(/:root\s*\{([\s\S]*?)\n\}/)
  const darkMatch = source.match(/prefers-color-scheme:\s*dark[\s\S]*?:root\s*\{([\s\S]*?)\n\s*\}/)
  if (!rootMatch || !darkMatch) {
    fail('Unable to locate light and dark token blocks')
    console.log('Token contrast: FAIL (missing token blocks)')
    return
  }

  const light = parseVars(rootMatch[1])
  const dark = { ...light, ...parseVars(darkMatch[1]) }
  const pairs = [
    ['foreground', 'background'],
    ['card-foreground', 'card'],
    ['primary-foreground', 'primary'],
    ['secondary-foreground', 'secondary'],
    ['muted-foreground', 'muted'],
    ['accent-foreground', 'accent'],
    ['destructive-foreground', 'destructive'],
  ]
  let lowest = Number.POSITIVE_INFINITY
  let issueCount = 0

  for (const [mode, vars] of [['light', light], ['dark', dark]]) {
    for (const [fg, bg] of pairs) {
      const ratio = contrast(resolveVar(vars, vars[fg]), resolveVar(vars, vars[bg]))
      lowest = Math.min(lowest, ratio)
      if (ratio < 4.5) {
        issueCount += 1
        fail(`${mode} ${fg}/${bg} contrast ${ratio.toFixed(2)} is below 4.5`)
      }
    }
  }

  console.log(`Token contrast: ${issueCount === 0 ? 'PASS' : 'FAIL'} (lowest ${lowest.toFixed(2)}:1)`)
}

async function auditTouchTargets() {
  const checks = [
    [tokensPath, /--touch-target:\s*44px;/, 'touch target token is 44px'],
    [path.join(styleDir, 'parts', 'base.css'), /button:not\(\.info-tooltip-trigger\)[\s\S]*min-height:\s*var\(--touch-target\);/, 'base interactive controls use touch target'],
    [path.join(styleDir, 'parts', 'components.css'), /\.info-tooltip-trigger\s*\{[\s\S]*?min-height:\s*var\(--touch-target\);/, 'tooltip trigger has 44px hit area'],
    [path.join(styleDir, 'parts', 'components.css'), /\.watchlist-dnd-toggle\s*\{[\s\S]*?min-height:\s*var\(--touch-target\);/, 'watchlist DnD label has 44px hit area'],
    [path.join(styleDir, 'parts', 'ui.css'), /\.ui-button-sm\s*\{[\s\S]*?min-height:\s*var\(--touch-target\);/, 'small shadcn-style button keeps 44px hit area'],
  ]
  let issueCount = 0

  for (const [file, pattern, label] of checks) {
    const source = await readFile(file, 'utf8')
    if (!pattern.test(source)) {
      issueCount += 1
      fail(`${relative(file)} missing ${label}`)
    }
  }

  console.log(`Touch targets: ${issueCount === 0 ? 'PASS' : 'FAIL'} (${checks.length - issueCount}/${checks.length} checks)`)
}

async function auditMobileTextHygiene() {
  const basePath = path.join(styleDir, 'parts', 'base.css')
  const tokenSource = await readFile(tokensPath, 'utf8')
  const baseSource = await readFile(basePath, 'utf8')
  const checks = [
    [tokensPath, /html\s*\{[^}]*text-size-adjust:\s*100%;[^}]*-webkit-text-size-adjust:\s*100%;[^}]*\}/, 'html locks mobile text-size adjustment at 100%'],
    [basePath, /button,\s*input,\s*select,\s*textarea\s*\{[^}]*font:\s*inherit;[^}]*color:\s*inherit;[^}]*\}/, 'form controls inherit typography and color'],
    [basePath, /p,\s*li,\s*dd,\s*blockquote\s*\{[^}]*overflow-wrap:\s*(?:break-word|anywhere);[^}]*\}/, 'long body text can wrap without horizontal overflow'],
  ]
  let issueCount = 0

  for (const [file, pattern, label] of checks) {
    const source = file === tokensPath ? tokenSource : baseSource
    if (!pattern.test(source)) {
      issueCount += 1
      fail(`${relative(file)} missing ${label}`)
    }
  }

  console.log(`Mobile text hygiene: ${issueCount === 0 ? 'PASS' : 'FAIL'} (${checks.length - issueCount}/${checks.length} checks)`)
}

async function auditCssImports() {
  const source = await readFile(globalCssPath, 'utf8')
  const imports = [...source.matchAll(/@import\s+['"](.+?)['"];/g)].map((match) => match[1])
  let issueCount = 0

  for (const importPath of imports) {
    try {
      await readFile(path.join(path.dirname(globalCssPath), importPath))
    } catch {
      issueCount += 1
      fail(`${relative(globalCssPath)} imports missing stylesheet ${importPath}`)
    }
  }

  const scrollbarBlocks = source.match(/\*::-webkit-scrollbar\b/g)?.length ?? 0
  if (scrollbarBlocks > 1) {
    issueCount += 1
    fail(`${relative(globalCssPath)} contains duplicate global scrollbar imports`)
  }

  console.log(`CSS imports: ${issueCount === 0 ? 'PASS' : 'FAIL'} (${imports.length} imports)`)
}

async function auditHydrationMode() {
  const mainSource = await readFile(path.join(srcDir, 'main.tsx'), 'utf8')
  let issueCount = 0
  if (/hydrateRoot\s*\(/.test(mainSource)) {
    issueCount += 1
    fail('src/main.tsx uses hydrateRoot; hydration-sensitive render-time values require SSR-safe handling')
  }
  if (!/createRoot\s*\(/.test(mainSource)) {
    issueCount += 1
    fail('src/main.tsx does not use createRoot for the current client-rendered app')
  }
  console.log(`Hydration mode: ${issueCount === 0 ? 'PASS' : 'FAIL'} (client-rendered createRoot)`)
}

await auditJsxAccessibility()
await auditSvgAccessibility()
await auditDecorativeElements()
await auditMenuKeyboardSupport()
await auditFocusVisible()
await auditForbiddenSourcePatterns()
await auditDarkModeBrowserChrome()
await auditTokenContrast()
await auditTouchTargets()
await auditMobileTextHygiene()
await auditCssImports()
await auditHydrationMode()

if (failures.length) {
  console.error('\nUI audit failures:')
  for (const message of failures) {
    console.error(`- ${message}`)
  }
}

if (failed) {
  process.exitCode = 1
}
