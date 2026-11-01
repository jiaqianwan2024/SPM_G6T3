-- TC-SPM11-AC02 (SPM-11): The attendee registers only themselves (name prefilled and editable, email locked); a blank mandatory field blocks submit with inline validation
-- Automated in e2e/spm11.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM11-AC02
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
