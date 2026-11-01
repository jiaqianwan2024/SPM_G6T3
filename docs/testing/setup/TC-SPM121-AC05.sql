-- TC-SPM121-AC05 (SPM-121): The organiser sees the event waiting on the safety review or with safety changes requested
-- Automated in e2e/spm121.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM121-AC05
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
