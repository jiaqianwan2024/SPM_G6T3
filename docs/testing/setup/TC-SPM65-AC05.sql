-- TC-SPM65-AC05 (SPM-65): A coordinator sees only their assigned requests (SPM-117)
-- Automated in e2e/spm65.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM65-AC05
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
