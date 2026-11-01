-- TC-SPM122-AC01b (SPM-122): Clashes shown in the venue catalogue once new times are saved
-- Automated in e2e/spm122.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM122-AC01b
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
