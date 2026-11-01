-- TC-SPM112-AC04 (SPM-112): Touching event times conflict when setup or turnaround overlap
-- Automated in e2e/spm112.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM112-AC04
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
