-- How well each movement was done and the final verdict of a finished attempt: the average quality of the six
-- movements decides (80 % or more is a correct wash). Numbers only, no images.
ALTER TABLE friction_step_validation ADD COLUMN quality_pct INTEGER
