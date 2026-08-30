-- Isolated legacy studbook schema.
--
-- Column names deliberately mirror the Frappe fieldnames in the Horse doctype,
-- so the bridge can SELECT straight into FIELD_MAP without aliasing. A real
-- legacy system would name them differently; when that day comes the aliases
-- live in one SELECT and nothing downstream moves.
--
-- Audit tables follow Hibernate Envers defaults: <table>_aud carrying rev +
-- revtype, and a single revinfo holding the revision clock.
--   revtype: 0 = ADD, 1 = MOD, 2 = DEL

BEGIN;

DROP TABLE IF EXISTS name_log_aud, ownership_log_aud, horse_aud,
                     name_log, ownership_log, horse, horse_owner, revinfo CASCADE;

-- ---------------------------------------------------------------- revisions
CREATE TABLE revinfo (
	rev      bigserial PRIMARY KEY,
	revtstmp bigint          -- epoch millis, as Envers writes it
);

-- ------------------------------------------------------------------ owners
CREATE TABLE horse_owner (
	id            bigserial PRIMARY KEY,
	owner_code    text UNIQUE,          -- the OWN-##### series
	owner_name_ar text NOT NULL,
	owner_name_en text NOT NULL,
	national_id   text,
	passport_no   text,
	phone         text,
	email         text,
	city          text,
	address       text
);

-- ------------------------------------------------------------------- horses
CREATE TABLE horse (
	id               bigserial PRIMARY KEY,
	registration_no  text UNIQUE NOT NULL,   -- LY-YYYY-##### , the Frappe docname

	-- identity
	name_ar          text NOT NULL,
	name_en          text NOT NULL,
	ueln_no          text,
	microchip_no     text,
	origin           text NOT NULL,          -- Local | Imported
	gender           text NOT NULL,          -- Male | Female | Gelding
	color            text,
	breed            text,
	date_of_birth    date,
	place_of_birth   text,
	current_location text,
	life_status      text,                   -- Alive | Deceased
	death_date       date,
	notification_date date,

	-- pedigree: sire
	sire_name_ar        text,
	sire_name_en        text,
	sire_registration_no text,
	sire_origin         text,
	sire_date_of_birth  date,
	sire_place_of_birth text,
	sire_color          text,
	sire_breed          text,
	sire_microchip_no   text,

	-- pedigree: dam
	dam_name_ar         text,
	dam_name_en         text,
	dam_registration_no text,
	dam_origin          text,
	dam_date_of_birth   date,
	dam_place_of_birth  text,
	dam_color           text,
	dam_breed           text,
	dam_microchip_no    text,

	-- current owner, denormalised exactly as the doctype holds it
	owner_name_ar     text,
	owner_name_en     text,
	owner_national_id text,
	owner_phone       text,
	owner_city        text,
	owner_address     text,
	owner_since       date,

	-- breeder
	breeder_name_ar     text,
	breeder_name_en     text,
	breeder_national_id text,
	breeder_phone       text,
	breeder_city        text,
	breeder_address     text,

	status text                              -- Not Yet | Partially Completed | Completed
);

CREATE INDEX horse_name_en_idx ON horse (lower(name_en));
CREATE INDEX horse_name_ar_idx ON horse (name_ar);

-- --------------------------------------------------- ownership / name logs
CREATE TABLE ownership_log (
	id                bigserial PRIMARY KEY,
	horse_id          bigint NOT NULL REFERENCES horse(id) ON DELETE CASCADE,
	owner_name_en     text NOT NULL,
	owner_national_id text,
	from_date         date,
	to_date           date,
	idx               int NOT NULL DEFAULT 1   -- child-table ordering
);

CREATE TABLE name_log (
	id         bigserial PRIMARY KEY,
	horse_id   bigint NOT NULL REFERENCES horse(id) ON DELETE CASCADE,
	name_ar    text,
	name_en    text,
	changed_on date,
	idx        int NOT NULL DEFAULT 1
);

CREATE INDEX ownership_log_horse_idx ON ownership_log (horse_id);
CREATE INDEX name_log_horse_idx      ON name_log (horse_id);

-- ------------------------------------------------------------ audit tables
CREATE TABLE horse_aud (
	rev     bigint NOT NULL REFERENCES revinfo(rev),
	revtype smallint NOT NULL,
	id      bigint NOT NULL,

	registration_no text,
	name_ar text, name_en text, ueln_no text, microchip_no text,
	origin text, gender text, color text, breed text,
	date_of_birth date, place_of_birth text, current_location text,
	life_status text, death_date date, notification_date date,

	sire_name_ar text, sire_name_en text, sire_registration_no text,
	sire_origin text, sire_date_of_birth date, sire_place_of_birth text,
	sire_color text, sire_breed text, sire_microchip_no text,

	dam_name_ar text, dam_name_en text, dam_registration_no text,
	dam_origin text, dam_date_of_birth date, dam_place_of_birth text,
	dam_color text, dam_breed text, dam_microchip_no text,

	owner_name_ar text, owner_name_en text, owner_national_id text,
	owner_phone text, owner_city text, owner_address text, owner_since date,

	breeder_name_ar text, breeder_name_en text, breeder_national_id text,
	breeder_phone text, breeder_city text, breeder_address text,

	status text,
	PRIMARY KEY (id, rev)
);

CREATE TABLE ownership_log_aud (
	rev     bigint NOT NULL REFERENCES revinfo(rev),
	revtype smallint NOT NULL,
	id      bigint NOT NULL,
	horse_id bigint,
	owner_name_en text,
	owner_national_id text,
	from_date date,
	to_date   date,
	idx int,
	PRIMARY KEY (id, rev)
);

CREATE TABLE name_log_aud (
	rev     bigint NOT NULL REFERENCES revinfo(rev),
	revtype smallint NOT NULL,
	id      bigint NOT NULL,
	horse_id bigint,
	name_ar text,
	name_en text,
	changed_on date,
	idx int,
	PRIMARY KEY (id, rev)
);

COMMIT;
