-- TC-SPM120-AC01 (SPM-120): Review only after venue and technical are confirmed / Venue Staff and technical support send their confirmed arrangements; the review opens once both are in (Week 7 change 6)
-- Automated in e2e/spm120.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM120-AC01
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
