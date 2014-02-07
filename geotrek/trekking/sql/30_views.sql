DROP VIEW IF EXISTS o_v_itineraire;
CREATE VIEW o_v_itineraire AS (
	SELECT e.geom, i.*
	FROM o_t_itineraire AS i, e_t_evenement AS e
	WHERE i.evenement = e.id
	AND e.supprime = FALSE
);

DROP VIEW IF EXISTS o_v_poi;
CREATE VIEW o_v_poi AS (
	SELECT e.geom, i.*
	FROM o_t_poi AS i, e_t_evenement AS e
	WHERE i.evenement = e.id
	AND e.supprime = FALSE
);