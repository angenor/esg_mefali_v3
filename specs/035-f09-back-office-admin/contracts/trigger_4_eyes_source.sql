-- F09 — Trigger 4-yeux validation source
-- Bloque la transition pending → verified si verified_by_user_id == captured_by_user_id

CREATE OR REPLACE FUNCTION before_verify_source_check_different_admin()
RETURNS TRIGGER AS $$
BEGIN
    -- Only fire on pending -> verified transition
    IF NOT (OLD.verification_status = 'pending' AND NEW.verification_status = 'verified') THEN
        RETURN NEW;
    END IF;

    IF NEW.verified_by_user_id IS NULL THEN
        RAISE EXCEPTION
            '4-eyes principle: verified_by_user_id required'
            USING ERRCODE = 'P0001';
    END IF;

    IF NEW.verified_by_user_id = OLD.captured_by_user_id THEN
        RAISE EXCEPTION
            '4-eyes principle violated: verifier (%) must differ from creator (%)',
            NEW.verified_by_user_id, OLD.captured_by_user_id
            USING ERRCODE = 'P0001';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sources_before_verify ON sources;
CREATE TRIGGER trg_sources_before_verify
    BEFORE UPDATE ON sources
    FOR EACH ROW
    EXECUTE FUNCTION before_verify_source_check_different_admin();
