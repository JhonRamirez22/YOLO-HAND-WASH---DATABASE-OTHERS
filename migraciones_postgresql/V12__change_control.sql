-- Change control for the protocol profile and the model (R-16, R-17).
-- Profile versions stay append-only; they now carry the reason, an approval state and, for rollbacks, the
-- version they copy. A model is "sin evidencia" until a validation report is registered against its sha256.
ALTER TABLE protocol_profiles ADD COLUMN reason VARCHAR(200);
