-- TC-SPM58-AC03 (SPM-58): Unresolved unavailable or shortfall lines
-- Automated in e2e/spm58.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM58-AC03
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
