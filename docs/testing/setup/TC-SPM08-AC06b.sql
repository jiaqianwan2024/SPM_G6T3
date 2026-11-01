-- TC-SPM08-AC06b (SPM-8): Overlapping unavailability blocks approval, shows an error, request stays pending
-- Automated in e2e/spm08.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM08-AC06b
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
