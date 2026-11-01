-- TC-SPM10-AC04 (SPM-10): Rejected, out of the pending queue, no longer approvable or changeable
-- Automated in e2e/spm10.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM10-AC04
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
