-- TC-SPM116-AC05 (SPM-116): The assigned coordinator is notified before the hold expires
-- Automated in e2e/spm116.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM116-AC05
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
