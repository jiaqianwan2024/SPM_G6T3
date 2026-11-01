import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Writes one line per test to test-reports/e2e.jsonl. scripts/test_report.py joins
// these with docs/testing/test-cases.csv to fill the results half of the template.

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const OUTPUT = path.join(ROOT, 'test-reports', 'e2e.jsonl')
// Playwright colours its error messages; the CSV wants plain text.
const ANSI = /\u001b\[[0-9;]*m/g

export default class ResultsReporter {
  constructor() {
    this.rows = []
  }

  onTestEnd(test, result) {
    // With retries this runs once per attempt; the last attempt is the result.
    const row = {
      title: test.title,
      // titlePath is [root, project, file, ...describe blocks, title]; keep the describes and title.
      path: test.titlePath().slice(3).join(' › '),
      file: path.relative(ROOT, test.location.file).split(path.sep).join('/'),
      status: result.status,
      expectedStatus: test.expectedStatus,
      retry: result.retry,
      durationMs: result.duration,
      error: (result.error?.message || '').replace(ANSI, '').split('\n').find((line) => line.trim()) || '',
      finishedAt: new Date(result.startTime.getTime() + result.duration).toISOString(),
    }
    const index = this.rows.findIndex((seen) => seen.path === row.path && seen.file === row.file)
    if (index === -1) this.rows.push(row)
    else this.rows[index] = row
  }

  onEnd() {
    fs.mkdirSync(path.dirname(OUTPUT), { recursive: true })
    fs.writeFileSync(OUTPUT, this.rows.map((row) => JSON.stringify(row)).join('\n') + (this.rows.length ? '\n' : ''))
  }

  printsToStdio() {
    return false
  }
}
