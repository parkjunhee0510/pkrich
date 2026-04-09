import { copyFileSync, existsSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const webDir = resolve(scriptDir, '..')
const distDir = resolve(webDir, 'dist')
const indexHtml = resolve(distDir, 'index.html')
const fallbackHtml = resolve(distDir, '404.html')

if (!existsSync(indexHtml)) {
  throw new Error(`Missing build artifact: ${indexHtml}`)
}

mkdirSync(dirname(fallbackHtml), { recursive: true })
copyFileSync(indexHtml, fallbackHtml)
