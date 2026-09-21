-- The StudLib studbook schema, as far as HMS reads it.
--
-- Column names, types and enum values come from the StudLib Data Specification
-- 1.01. This is a subset, not the whole database: the tables HMS actually
-- SELECTs from, plus the audit scaffolding that proves the shape is right.
--
-- Deliberately left out, because nothing here reads them: covering_agreement,
-- covering_certificate, covering_result, season, laboratory*, the ~24 horse
-- marking collection tables, refresh_token, token_blacklist, email_log,
-- forbidden_name and studbook_generation_task.
--
-- Audit tables follow Hibernate Envers defaults: <table>_aud carrying rev +
-- revtype, and a single revision_info holding the revision clock.
--   revtype: 0 = ADD, 1 = MOD, 2 = DEL

BEGIN;

DROP TABLE IF EXISTS
	event_new_owner_aud, event_old_owner_aud, horse_breeder_aud, horse_owner_aud,
	event_aud, horse_aud, owner_aud,
	event_new_owner, event_old_owner, event, event_type,
	file, horse_breeder, horse_owner, horse,
	owner, book_type, horse_color, city, country,
	application_user, laboratory, revision_info CASCADE;

-- fuzzy owner search, as the specification calls for
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------------------------------------------------------------- revisions
CREATE TABLE revision_info (
	id                 bigserial PRIMARY KEY,
	revision_timestamp bigint,          -- epoch millis, as Envers writes it
	custom_timestamp   timestamp(6),
	username           varchar(255),
	usern_fullname     varchar(255),
	ip_address         varchar(255)
);

CREATE INDEX idx_revision_info_custom_timestamp ON revision_info (custom_timestamp DESC);
CREATE INDEX idx_revision_info_username         ON revision_info (username);

-- --------------------------------------------------------------- reference
CREATE TABLE country (
	id                bigserial PRIMARY KEY,
	creation_date     timestamp(6),
	modification_date timestamp(6),
	version           integer NOT NULL DEFAULT 0,
	name              varchar(255) NOT NULL UNIQUE,
	alpha2            varchar(2)   NOT NULL UNIQUE,
	alpha3            varchar(3)   NOT NULL UNIQUE,
	code              varchar(3)   NOT NULL UNIQUE,
	local             boolean      NOT NULL DEFAULT false
);

-- exactly one country may be the home country
CREATE UNIQUE INDEX unique_local_country ON country (local) WHERE (local = true);

CREATE TABLE city (
	name varchar(255) PRIMARY KEY
);

CREATE TABLE book_type (
	id                bigserial PRIMARY KEY,
	creation_date     timestamp(6),
	modification_date timestamp(6),
	version           integer NOT NULL DEFAULT 0,
	code              varchar(128),
	authority         varchar(255),
	horse_breed       varchar(255) NOT NULL
		CHECK (horse_breed IN ('ARABIAN', 'THOROUGHBRED')),
	libyan            boolean DEFAULT false,
	country_id        bigint REFERENCES country(id)
);

CREATE TABLE horse_color (
	id                bigserial PRIMARY KEY,
	creation_date     timestamp(6),
	modification_date timestamp(6),
	version           integer NOT NULL DEFAULT 0,
	name              varchar(255) NOT NULL,
	short_name        varchar(255) NOT NULL,
	horse_breed       varchar(255) NOT NULL
		CHECK (horse_breed IN ('ARABIAN', 'THOROUGHBRED')),
	validation_rule   varchar(255)
		CHECK (validation_rule IS NULL
		       OR validation_rule IN ('BOTH_PARENTS', 'AT_LEAST_ONE_PARENT')),
	UNIQUE (horse_breed, name),
	UNIQUE (horse_breed, short_name)
);

CREATE TABLE laboratory (
	id                bigserial PRIMARY KEY,
	creation_date     timestamp(6),
	modification_date timestamp(6),
	version           integer NOT NULL DEFAULT 0,
	name              varchar(255)
);

-- only the columns the horse join needs; authentication is StudLib's business
CREATE TABLE application_user (
	id                bigserial PRIMARY KEY,
	creation_date     timestamp(6),
	modification_date timestamp(6),
	version           integer NOT NULL DEFAULT 0,
	email             varchar(128) NOT NULL,
	password          varchar(128) NOT NULL DEFAULT '',
	full_name         varchar(256),
	system_role       varchar(24)  NOT NULL DEFAULT 'VIEWER',
	breed             varchar(24)  NOT NULL DEFAULT 'ARABIAN',
	deleted           boolean      NOT NULL DEFAULT false,
	reset_password_token varchar(64),
	laboratory_id     bigint REFERENCES laboratory(id),
	UNIQUE (email, breed)
);

-- --------------------------------------------------------------- ownership
CREATE TABLE owner (
	id                 bigserial PRIMARY KEY,
	creation_date      timestamp(6),
	modification_date  timestamp(6),
	version            integer NOT NULL DEFAULT 0,
	full_name          varchar(255) NOT NULL,
	suffix             varchar(255) UNIQUE,
	business           boolean DEFAULT false,
	business_number    varchar(128),
	national_id_number varchar(128),
	farm_name          varchar(255),
	phone              varchar(255),
	note               text,
	street             varchar(255),
	city               varchar(255),
	postal_code        varchar(255),
	region             varchar(255),
	latitude           double precision,
	longitude          double precision,
	country_id         bigint REFERENCES country(id),
	UNIQUE (full_name, country_id, city)
);

CREATE INDEX idx_owner_full_name_trgm          ON owner USING gin (lower(full_name) gin_trgm_ops);
CREATE INDEX idx_owner_business_number_trgm    ON owner USING gin (lower(business_number) gin_trgm_ops);
CREATE INDEX idx_owner_national_id_number_trgm ON owner USING gin (lower(national_id_number) gin_trgm_ops);
CREATE INDEX idx_owner_suffix_trgm             ON owner USING gin (lower(suffix) gin_trgm_ops);

-- ------------------------------------------------------------------- horse
CREATE TABLE horse (
	id                bigserial PRIMARY KEY,
	creation_date     timestamp(6),
	modification_date timestamp(6),
	version           integer NOT NULL DEFAULT 0,

	-- identity
	name         varchar(255) NOT NULL,
	name_suffix  varchar(10),
	local_name   varchar(255),
	breed        varchar(255) NOT NULL
		CHECK (breed IN ('ARABIAN', 'THOROUGHBRED')),
	sex          varchar(255) NOT NULL
		CHECK (sex IN ('MALE', 'FEMALE', 'STALLION', 'BROODMARE',
		               'GELDING', 'CRYPTORCHID', 'MONORCHID')),
	status       varchar(255) NOT NULL
		CHECK (status IN ('NEW_FOAL', 'NEW_IMPORTED', 'WAITING_FOR_MARKING_DATA',
		                  'WAITING_FOR_LABORATORY', 'LABORATORY_DATA_ENTERED',
		                  'REGISTER_IN_STUDBOOK', 'REJECTED', 'EXTERNAL')),
	horse_classification varchar(255)
		CHECK (horse_classification IS NULL
		       OR horse_classification IN ('RACING', 'JUMPING', 'BEAUTY', 'UNKNOWN')),
	uuid         uuid NOT NULL UNIQUE,

	-- registry numbers
	ueln                 varchar(15),
	registry_id          varchar(255),
	previous_registry_id varchar(255),
	legacy_registry_id   varchar(255),
	legacy_ueln          varchar(15),

	-- identification
	transponder_code        varchar(15),
	second_transponder_code varchar(255),
	transponder_site        varchar(255),
	blood_code              varchar(255),
	strain                  varchar(255),

	-- dates
	date_of_birth        date,
	date_of_death        date,
	date_of_registration date,
	date_of_importing    date,
	date_of_exporting    date,
	date_of_control      date,
	date_of_declaration  date,

	dna_sample_exists    boolean DEFAULT false,
	imported_from_file   boolean DEFAULT false,
	generated_registry_id boolean DEFAULT false,

	-- studbook placement
	book_number                   integer,
	book_page                     integer,
	book_appendix_number          integer,
	previous_book_number          integer,
	previous_book_page            integer,
	previous_book_appendix_number integer,

	notes text,

	-- foreign keys
	father_id             bigint REFERENCES horse(id),
	mother_id             bigint REFERENCES horse(id),
	birthplace_country_id bigint REFERENCES country(id),
	import_country_id     bigint REFERENCES country(id),
	export_country_id     bigint REFERENCES country(id),
	book_type_id          bigint REFERENCES book_type(id),
	previous_book_type_id bigint REFERENCES book_type(id),
	color_id              bigint REFERENCES horse_color(id),
	controlled_by_id      bigint REFERENCES application_user(id)
);

CREATE INDEX horse_registry_id_idx  ON horse (registry_id);
CREATE INDEX horse_transponder_idx  ON horse (transponder_code);
CREATE INDEX horse_father_idx       ON horse (father_id);
CREATE INDEX horse_mother_idx       ON horse (mother_id);

-- a horse may be owned by several parties at once
CREATE TABLE horse_owner (
	horse_id bigint NOT NULL REFERENCES horse(id) ON DELETE CASCADE,
	owner_id bigint NOT NULL REFERENCES owner(id),
	PRIMARY KEY (horse_id, owner_id)
);

-- the owners of the dam at the time of foaling
CREATE TABLE horse_breeder (
	horse_id bigint NOT NULL REFERENCES horse(id) ON DELETE CASCADE,
	owner_id bigint NOT NULL REFERENCES owner(id),
	PRIMARY KEY (horse_id, owner_id)
);

-- ------------------------------------------------------------------ events
CREATE TABLE event_type (
	id                bigserial PRIMARY KEY,
	creation_date     timestamp(6),
	modification_date timestamp(6),
	version           integer NOT NULL DEFAULT 0,
	type              varchar(255)
		CHECK (type IS NULL OR type IN ('CHANGE_OWNER', 'FOAL_ABORTION', 'NEW_FOAL',
		                                'DEATH', 'IMPORT', 'EXPORT', 'GELDING', 'COVERED')),
	description       varchar(255),
	selectable        boolean NOT NULL DEFAULT true
);

CREATE TABLE event (
	id                bigserial PRIMARY KEY,
	creation_date     timestamp(6),
	modification_date timestamp(6),
	version           integer NOT NULL DEFAULT 0,
	date                   date,
	description            varchar(255),
	additional_information varchar(255),
	cover     boolean,
	pregnant  boolean,
	twins     boolean,
	horse_sex smallint CHECK (horse_sex IS NULL OR horse_sex BETWEEN 0 AND 6),
	type_id             bigint REFERENCES event_type(id),
	horse_primary_id    bigint REFERENCES horse(id),
	horse_secondary_id  bigint REFERENCES horse(id),
	horse_offspring_id  bigint REFERENCES horse(id),
	country_id          bigint REFERENCES country(id)
);

CREATE INDEX event_primary_idx ON event (horse_primary_id);
CREATE INDEX event_type_idx    ON event (type_id);

CREATE TABLE event_old_owner (
	event_id bigint NOT NULL REFERENCES event(id) ON DELETE CASCADE,
	owner_id bigint NOT NULL REFERENCES owner(id),
	PRIMARY KEY (event_id, owner_id)
);

CREATE TABLE event_new_owner (
	event_id bigint NOT NULL REFERENCES event(id) ON DELETE CASCADE,
	owner_id bigint NOT NULL REFERENCES owner(id),
	PRIMARY KEY (event_id, owner_id)
);

-- ------------------------------------------------------------------- files
CREATE TABLE file (
	id                bigserial PRIMARY KEY,
	creation_date     timestamp(6),
	modification_date timestamp(6),
	version           integer NOT NULL DEFAULT 0,
	file_type     varchar(31)  NOT NULL,
	file_name     varchar(255) NOT NULL,
	file_path     varchar(255) NOT NULL UNIQUE,
	file_size     bigint       NOT NULL,
	mime_type     varchar(255) NOT NULL,
	-- 0 = identification document, 1 = certificate, 2 = other
	document_type smallint CHECK (document_type IS NULL OR document_type BETWEEN 0 AND 2),
	is_avatar     boolean,
	horse_id      bigint REFERENCES horse(id)
);

CREATE INDEX file_horse_idx ON file (horse_id);

-- ------------------------------------------------------------ audit tables
-- One per audited entity, mirroring the base table plus rev/revtype. Only the
-- entities HMS reads are mirrored here; nothing fills them automatically,
-- there are no triggers. sample_data.sql shows the pattern.
CREATE TABLE horse_aud (
	rev     bigint NOT NULL REFERENCES revision_info(id),
	revtype smallint NOT NULL,
	id      bigint NOT NULL,
	name varchar(255), name_suffix varchar(10), local_name varchar(255),
	breed varchar(255), sex varchar(255), status varchar(255),
	horse_classification varchar(255), uuid uuid,
	ueln varchar(15), registry_id varchar(255), previous_registry_id varchar(255),
	legacy_registry_id varchar(255), legacy_ueln varchar(15),
	transponder_code varchar(15), second_transponder_code varchar(255),
	transponder_site varchar(255), blood_code varchar(255), strain varchar(255),
	date_of_birth date, date_of_death date, date_of_registration date,
	date_of_importing date, date_of_exporting date, date_of_control date,
	date_of_declaration date, dna_sample_exists boolean,
	book_number integer, book_page integer, book_appendix_number integer,
	previous_book_number integer, previous_book_page integer,
	previous_book_appendix_number integer,
	notes text,
	father_id bigint, mother_id bigint, birthplace_country_id bigint,
	import_country_id bigint, export_country_id bigint,
	book_type_id bigint, previous_book_type_id bigint, color_id bigint,
	controlled_by_id bigint,
	PRIMARY KEY (rev, id)
);

CREATE INDEX idx_horse_aud_status_registration ON horse_aud (status, date_of_registration);

CREATE TABLE owner_aud (
	rev     bigint NOT NULL REFERENCES revision_info(id),
	revtype smallint NOT NULL,
	id      bigint NOT NULL,
	full_name varchar(255), suffix varchar(255), business boolean,
	business_number varchar(128), national_id_number varchar(128),
	farm_name varchar(255), phone varchar(255), note text,
	street varchar(255), city varchar(255), postal_code varchar(255),
	region varchar(255), latitude double precision, longitude double precision,
	country_id bigint,
	PRIMARY KEY (rev, id)
);

CREATE TABLE event_aud (
	rev     bigint NOT NULL REFERENCES revision_info(id),
	revtype smallint NOT NULL,
	id      bigint NOT NULL,
	date date, description varchar(255), additional_information varchar(255),
	cover boolean, pregnant boolean, twins boolean, horse_sex smallint,
	type_id bigint, horse_primary_id bigint, horse_secondary_id bigint,
	horse_offspring_id bigint, country_id bigint,
	PRIMARY KEY (rev, id)
);

-- collection tables key on (rev, entity_id, collection_element)
CREATE TABLE horse_owner_aud (
	rev     bigint NOT NULL REFERENCES revision_info(id),
	revtype smallint NOT NULL,
	horse_id bigint NOT NULL,
	owner_id bigint NOT NULL,
	PRIMARY KEY (rev, horse_id, owner_id)
);

CREATE TABLE horse_breeder_aud (
	rev     bigint NOT NULL REFERENCES revision_info(id),
	revtype smallint NOT NULL,
	horse_id bigint NOT NULL,
	owner_id bigint NOT NULL,
	PRIMARY KEY (rev, horse_id, owner_id)
);

CREATE TABLE event_old_owner_aud (
	rev     bigint NOT NULL REFERENCES revision_info(id),
	revtype smallint NOT NULL,
	event_id bigint NOT NULL,
	owner_id bigint NOT NULL,
	PRIMARY KEY (rev, event_id, owner_id)
);

CREATE TABLE event_new_owner_aud (
	rev     bigint NOT NULL REFERENCES revision_info(id),
	revtype smallint NOT NULL,
	event_id bigint NOT NULL,
	owner_id bigint NOT NULL,
	PRIMARY KEY (rev, event_id, owner_id)
);

-- ------------------------------------------------------------------- views
-- The specification ships these; HMS does not read them yet, but the shape of
-- vhorse is what tells you whether a horse counts as Local or Imported.
CREATE VIEW vhorse AS
SELECT h.*,
       c.name AS color_name,
       CASE WHEN bc.local THEN 'LOCAL' ELSE 'IMPORTED' END AS origin,
       (SELECT count(*) FROM horse f
         WHERE f.father_id = h.id OR f.mother_id = h.id) AS offspring_count
FROM horse h
LEFT JOIN horse_color c ON c.id = h.color_id
LEFT JOIN country bc    ON bc.id = h.birthplace_country_id;

CREATE VIEW vhorse_event AS
SELECT e.id AS event_id, e.date, et.type AS event_type, e.description,
       h.id AS horse_id, h.uuid, h.name AS horse_name, h.registry_id
FROM event e
JOIN event_type et ON et.id = e.type_id
LEFT JOIN horse h  ON h.id = e.horse_primary_id;

-- ------------------------------------------------------------------ grants
-- The tables are dropped and recreated above, which takes their privileges
-- with them. Re-granting here keeps ./pg.sh reset from locking the sync out.
DO $$
BEGIN
	IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'studbook_ro') THEN
		GRANT USAGE ON SCHEMA public TO studbook_ro;
		GRANT SELECT ON ALL TABLES IN SCHEMA public TO studbook_ro;
		ALTER DEFAULT PRIVILEGES IN SCHEMA public
			GRANT SELECT ON TABLES TO studbook_ro;
	END IF;
END
$$;

COMMIT;
