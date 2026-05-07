-- F09 — Trigger publish gating
-- Bloque la transition draft → published si au moins une source liée n'est pas verified

CREATE OR REPLACE FUNCTION before_publish_check_sources_verified()
RETURNS TRIGGER AS $$
DECLARE
    offending_source_id UUID;
    offending_status VARCHAR;
    entity_type VARCHAR;
BEGIN
    -- Only fire on draft -> published transition
    IF NOT (OLD.publication_status = 'draft' AND NEW.publication_status = 'published') THEN
        RETURN NEW;
    END IF;

    entity_type := TG_TABLE_NAME;

    -- Iterate sources via entity_sources (table polymorphe)
    SELECT s.id, s.verification_status
        INTO offending_source_id, offending_status
    FROM sources s
    JOIN entity_sources es ON es.source_id = s.id
    WHERE es.entity_type = entity_type
      AND es.entity_id = NEW.id
      AND s.verification_status != 'verified'
    LIMIT 1;

    IF offending_source_id IS NOT NULL THEN
        RAISE EXCEPTION
            'cannot publish: source % has verification_status=%',
            offending_source_id, offending_status
            USING ERRCODE = 'P0001';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers (10 par table catalogue)
-- Pour chaque table dans : funds, intermediaries, offers, referentials, indicators, criteria, templates, emission_factors, simulation_factors, skills

-- Exemple pour funds :
DROP TRIGGER IF EXISTS trg_funds_before_publish ON funds;
CREATE TRIGGER trg_funds_before_publish
    BEFORE UPDATE ON funds
    FOR EACH ROW
    EXECUTE FUNCTION before_publish_check_sources_verified();

-- Répéter pour les 9 autres tables (intermediaries, offers, referentials, indicators, criteria, templates, emission_factors, simulation_factors, skills)
