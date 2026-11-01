-- TC-SPM78-AC04 (SPM-78): Release on confirmed requires reason and notifies
-- Automated in e2e/spm78.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM78-AC04
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
