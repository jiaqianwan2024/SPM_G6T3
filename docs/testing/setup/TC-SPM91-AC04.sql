-- TC-SPM91-AC04 (SPM-91): A full event leaves the list until a withdrawal frees a place; its own page says it is full
-- Automated in e2e/spm91.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM91-AC04
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
