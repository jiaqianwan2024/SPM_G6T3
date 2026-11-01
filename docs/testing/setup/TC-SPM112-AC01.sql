-- TC-SPM112-AC01 (SPM-112): Occupied window is start minus setup through end plus turnaround, from the venue's current times
-- Automated in e2e/spm112.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM112-AC01
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
