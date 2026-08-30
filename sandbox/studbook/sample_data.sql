-- Starter rows for the sandbox. Open in DBeaver as studbook_app and run the
-- whole script with Alt+X, or one statement at a time with Ctrl+Enter.
--
-- Edit the values freely: this is a fixture, not a migration. Re-running it is
-- safe, the ON CONFLICT clauses update in place rather than erroring.

-- ------------------------------------------------------------------ owners
INSERT INTO horse_owner (owner_code, owner_name_ar, owner_name_en, national_id,
                         phone, city, address)
VALUES
	('OWN-00001', 'محمد الفيتوري', 'Mohamed Al Fituri', '119820451122', '0912345678', 'Tripoli', 'Hay Al Andalus'),
	('OWN-00002', 'خالد المصراتي', 'Khaled Al Misrati', '119790332211', '0913456789', 'Misrata', 'Zawiyat Al Mahjoub')
ON CONFLICT (owner_code) DO NOTHING;

-- ------------------------------------------------------------------- horses
-- Only registration_no, name_ar, name_en, origin and gender are required.
INSERT INTO horse (registration_no, name_ar, name_en, ueln_no, microchip_no,
                   origin, gender, color, breed, date_of_birth, place_of_birth,
                   current_location, life_status,
                   sire_name_ar, sire_name_en, sire_registration_no, sire_origin,
                   sire_date_of_birth, sire_color, sire_breed,
                   dam_name_ar, dam_name_en, dam_registration_no, dam_origin,
                   dam_date_of_birth, dam_color, dam_breed,
                   owner_name_ar, owner_name_en, owner_national_id, owner_phone,
                   owner_city, owner_address, owner_since,
                   breeder_name_ar, breeder_name_en, breeder_national_id,
                   breeder_phone, breeder_city,
                   status)
VALUES
	('LY-2026-00001', 'الوثبة', 'Al Wathba', 'LY01201800001', '985197451334405',
	 'Local', 'Female', 'Grey', 'Arabian', '2018-02-16', 'مزرعة الوادي',
	 'مزرعة الوادي', 'Alive',
	 'مرواس', 'Marwas', 'LY-2010-00044', 'Local', '2010-05-02', 'Bay', 'Arabian',
	 'نورة', 'Noura', 'LY-2011-00071', 'Local', '2011-04-19', 'Grey', 'Arabian',
	 'محمد الفيتوري', 'Mohamed Al Fituri', '119820451122', '0912345678',
	 'Tripoli', 'Hay Al Andalus', '2019-01-10',
	 'سالم بن نايل', 'Salem Ben Nayel', '119750112233', '0914567890', 'Tripoli',
	 'Completed'),

	('LY-2026-00002', 'نجم الليل', 'Najm Al Layl', 'LY01201500002', '985142016061089',
	 'Imported', 'Male', 'Black', 'Arabian', '2015-08-15', 'Egypt',
	 'إسطبل الفرنسية', 'Alive',
	 'سيف النصر', 'Saif Al Nasr', 'EG-2008-00912', 'Imported', '2008-03-11', 'Black', 'Arabian',
	 'مسك', 'Misk', 'EG-2010-00318', 'Imported', '2010-06-23', 'Chestnut', 'Arabian',
	 'خالد المصراتي', 'Khaled Al Misrati', '119790332211', '0913456789',
	 'Misrata', 'Zawiyat Al Mahjoub', '2017-11-05',
	 NULL, NULL, NULL, NULL, NULL,
	 'Partially Completed')
ON CONFLICT (registration_no) DO NOTHING;

-- ------------------------------------------------- child tables (optional)
-- Cleared first so a second run replaces these rows instead of doubling them.
DELETE FROM ownership_log c USING horse h
WHERE h.id = c.horse_id AND h.registration_no = 'LY-2026-00001';

INSERT INTO ownership_log (horse_id, owner_name_en, owner_national_id, from_date, to_date, idx)
SELECT id, 'Ahmed Al Zwai', '119880776655', '2018-03-01', '2019-01-09', 1
FROM horse WHERE registration_no = 'LY-2026-00001';

INSERT INTO ownership_log (horse_id, owner_name_en, owner_national_id, from_date, to_date, idx)
SELECT id, 'Mohamed Al Fituri', '119820451122', '2019-01-10', NULL, 2
FROM horse WHERE registration_no = 'LY-2026-00001';

DELETE FROM name_log c USING horse h
WHERE h.id = c.horse_id AND h.registration_no = 'LY-2026-00001';

INSERT INTO name_log (horse_id, name_ar, name_en, changed_on, idx)
SELECT id, 'وثبة', 'Wathba', '2018-06-01', 1
FROM horse WHERE registration_no = 'LY-2026-00001';

-- --------------------------------------------------------- audit trail
-- Only worth writing for horses whose history you want to query. Each revision
-- is a row in revinfo plus a snapshot of the whole record in horse_aud.
--   revtype  0 = ADD  1 = MOD  2 = DEL
--
-- Cleared first, same reason as the child tables above.
DELETE FROM horse_aud a USING horse h
WHERE h.id = a.id AND h.registration_no = 'LY-2026-00001';

-- Revision 1: the horse as first registered, living somewhere else.
WITH r AS (
	INSERT INTO revinfo (revtstmp) VALUES (extract(epoch FROM timestamp '2018-03-01') * 1000)
	RETURNING rev
)
INSERT INTO horse_aud (rev, revtype, id, registration_no, name_ar, name_en,
                       origin, gender, color, date_of_birth, current_location, life_status,
                       owner_name_en, owner_national_id)
SELECT r.rev, 0, h.id, h.registration_no, h.name_ar, h.name_en,
       h.origin, h.gender, h.color, h.date_of_birth, 'إسطبل بنغازي', 'Alive',
       'Ahmed Al Zwai', '119880776655'
FROM horse h, r WHERE h.registration_no = 'LY-2026-00001';

-- Revision 2: sold, and moved to where it is now.
WITH r AS (
	INSERT INTO revinfo (revtstmp) VALUES (extract(epoch FROM timestamp '2019-01-10') * 1000)
	RETURNING rev
)
INSERT INTO horse_aud (rev, revtype, id, registration_no, name_ar, name_en,
                       origin, gender, color, date_of_birth, current_location, life_status,
                       owner_name_en, owner_national_id)
SELECT r.rev, 1, h.id, h.registration_no, h.name_ar, h.name_en,
       h.origin, h.gender, h.color, h.date_of_birth, h.current_location, h.life_status,
       h.owner_name_en, h.owner_national_id
FROM horse h, r WHERE h.registration_no = 'LY-2026-00001';

-- Read the trail back:
--   SELECT a.rev, a.revtype, a.current_location, a.owner_name_en,
--          to_timestamp(r.revtstmp / 1000)::date AS changed_on
--   FROM horse_aud a JOIN revinfo r USING (rev)
--   JOIN horse h ON h.id = a.id
--   WHERE h.registration_no = 'LY-2026-00001'
--   ORDER BY a.rev;
