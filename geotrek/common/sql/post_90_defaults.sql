-- AccessibilityAttachment
--------------------------
-- attachment_accessibility_file
ALTER TABLE common_accessibilityattachment ALTER COLUMN info_accessibility SET DEFAULT 'slope';
-- creation_date
ALTER TABLE common_accessibilityattachment ALTER COLUMN uuid SET DEFAULT gen_random_uuid();
-- creator
ALTER TABLE common_accessibilityattachment ALTER COLUMN author SET DEFAULT '';
ALTER TABLE common_accessibilityattachment ALTER COLUMN title SET DEFAULT '';
ALTER TABLE common_accessibilityattachment ALTER COLUMN legend SET DEFAULT '';
ALTER TABLE common_accessibilityattachment ALTER COLUMN date_insert SET DEFAULT now();
ALTER TABLE common_accessibilityattachment ALTER COLUMN date_update SET DEFAULT now();


-- Organism
-----------
-- organism
-- structure


-- FileType
-----------
-- type
-- structure


-- Attachment
-------------
-- creation_date
ALTER TABLE common_attachment ALTER COLUMN uuid SET DEFAULT gen_random_uuid();
ALTER TABLE common_attachment ALTER COLUMN attachment_file SET DEFAULT '';
ALTER TABLE common_attachment ALTER COLUMN attachment_video SET DEFAULT '';
ALTER TABLE common_attachment ALTER COLUMN attachment_link SET DEFAULT '';
-- filetype
-- creator
ALTER TABLE common_attachment ALTER COLUMN author SET DEFAULT '';
ALTER TABLE common_attachment ALTER COLUMN title SET DEFAULT '';
ALTER TABLE common_attachment ALTER COLUMN legend SET DEFAULT '';
ALTER TABLE common_attachment ALTER COLUMN starred SET DEFAULT False;
ALTER TABLE common_attachment ALTER COLUMN is_image SET DEFAULT False;
ALTER TABLE common_attachment ALTER COLUMN date_insert SET DEFAULT now();
ALTER TABLE common_attachment ALTER COLUMN date_update SET DEFAULT now();

-- Theme
--------
-- label
-- cirkwi
-- pictogram


-- RecordSource
---------------
-- name
-- website
-- pictogram


-- TargetPortal
---------------
-- name
-- website
ALTER TABLE common_targetportal ALTER COLUMN title SET DEFAULT '';
ALTER TABLE common_targetportal ALTER COLUMN description SET DEFAULT '';
ALTER TABLE common_targetportal ALTER COLUMN facebook_image_url SET DEFAULT '{{ FACEBOOK_IMAGE }}';
ALTER TABLE common_targetportal ALTER COLUMN facebook_image_width SET DEFAULT '{{ FACEBOOK_IMAGE_WIDTH }}';
ALTER TABLE common_targetportal ALTER COLUMN facebook_image_height SET DEFAULT '{{ FACEBOOK_IMAGE_HEIGHT }}';


-- ReservationSystem
--------------------
-- name


-- Label
--------
-- name
ALTER TABLE common_label ALTER COLUMN filter SET DEFAULT False;
ALTER TABLE common_label ALTER COLUMN advice SET DEFAULT '';
-- pictogram
