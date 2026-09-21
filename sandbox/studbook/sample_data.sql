-- Sample StudLib data: enough of everything HMS reads to exercise it.
--
-- Four horses (a local sire and dam, their foal, one imported), three owners,
-- both M:N tables, all eight event types with four real events, two files, and
-- a two-revision audit trail.
--
-- Re-runnable: it truncates first, so a second run replaces its rows rather
-- than doubling them.

BEGIN;

TRUNCATE
	event_new_owner_aud, event_old_owner_aud, horse_breeder_aud, horse_owner_aud,
	event_aud, horse_aud, owner_aud,
	event_new_owner, event_old_owner, event, event_type,
	file, horse_breeder, horse_owner, horse,
	owner, book_type, horse_color, city, country,
	application_user, laboratory, revision_info
RESTART IDENTITY CASCADE;

-- --------------------------------------------------------------- reference
INSERT INTO country (id, name, alpha2, alpha3, code, local) VALUES
	(1, 'Libya',  'LY', 'LBY', '434', true),
	(2, 'Egypt',  'EG', 'EGY', '818', false),
	(3, 'France', 'FR', 'FRA', '250', false);

INSERT INTO city (name) VALUES ('Tripoli'), ('Benghazi'), ('Misrata');

INSERT INTO horse_color (id, name, short_name, horse_breed, validation_rule) VALUES
	(1, 'Bay',      'b.',  'ARABIAN',      'AT_LEAST_ONE_PARENT'),
	(2, 'Grey',     'gr.', 'ARABIAN',      'AT_LEAST_ONE_PARENT'),
	(3, 'Chestnut', 'ch.', 'ARABIAN',      'BOTH_PARENTS'),
	(4, 'Black',    'bl.', 'ARABIAN',      NULL),
	(5, 'Bay',      'b.',  'THOROUGHBRED', 'AT_LEAST_ONE_PARENT'),
	(6, 'Chestnut', 'ch.', 'THOROUGHBRED', 'BOTH_PARENTS');

INSERT INTO book_type (id, code, authority, horse_breed, libyan, country_id) VALUES
	(1, 'LSB',  'Libyan Stud Book',                'ARABIAN',      true,  1),
	(2, 'WAHO', 'World Arabian Horse Organization','ARABIAN',      false, NULL),
	(3, 'LTB',  'Libyan Thoroughbred Book',        'THOROUGHBRED', true,  1);

INSERT INTO laboratory (id, name) VALUES (1, 'Veterinary Genetics Laboratory');

INSERT INTO application_user (id, email, password, full_name, system_role, breed) VALUES
	(1, 'vet@lsb.ly', 'x', 'Dr. Salem Ahmed', 'SECOND_LEVEL_EDITOR', 'ARABIAN');

-- --------------------------------------------------------------- ownership
INSERT INTO owner (id, full_name, suffix, business, business_number,
                   national_id_number, farm_name, phone, street, city,
                   postal_code, region, country_id) VALUES
	(1, 'Ahmed Al-Mansouri', 'ALM', false, NULL, '119880012345',
	    'Al-Mansouri Stud', '+218 91 000 0001', 'Gargaresh Road', 'Tripoli',
	    '11111', 'Tripoli', 1),
	(2, 'Fatima Al-Zawawi', 'FAZ', false, NULL, '219900054321',
	    NULL, '+218 92 000 0002', 'Street 17', 'Benghazi', '22222', 'Benghazi', 1),
	(3, 'Sahara Arabians Ltd', 'SAH', true, 'LY-BR-99001', NULL,
	    'Sahara Arabians', '+218 93 000 0003', 'Airport Road', 'Misrata',
	    '33333', 'Misrata', 1);

-- ------------------------------------------------------------------- horses
-- 1 sire, 2 dam, 3 their foal (still NEW_FOAL, so no registry_id yet),
-- 4 imported from Egypt
INSERT INTO horse (id, name, local_name, name_suffix, breed, sex, status,
                   horse_classification, uuid, ueln, registry_id,
                   previous_registry_id, transponder_code, strain,
                   date_of_birth, date_of_registration, date_of_control,
                   date_of_declaration, date_of_importing, dna_sample_exists,
                   book_number, book_page, notes,
                   father_id, mother_id, birthplace_country_id,
                   import_country_id, book_type_id, previous_book_type_id,
                   color_id, controlled_by_id) VALUES
	(1, 'Sahm Al-Sahra', 'سهم الصحراء', NULL, 'ARABIAN', 'STALLION',
	    'REGISTER_IN_STUDBOOK', 'RACING',
	    '11111111-1111-4111-8111-111111111111', '434002W00000001', 'AH-1001',
	    NULL, '985101000100001', 'Kuhailan',
	    '2016-03-12', '2018-01-10', '2016-09-01', '2016-04-01', NULL, true,
	    3, 45, 'Foundation sire.',
	    NULL, NULL, 1, NULL, 1, NULL, 1, 1),

	(2, 'Najma', 'نجمة', NULL, 'ARABIAN', 'BROODMARE',
	    'REGISTER_IN_STUDBOOK', 'BEAUTY',
	    '22222222-2222-4222-8222-222222222222', '434002W00000002', 'AH-1002',
	    NULL, '985101000100002', 'Saqlawi',
	    '2017-04-02', '2019-02-14', '2017-10-05', '2017-05-01', NULL, true,
	    3, 46, NULL,
	    NULL, NULL, 1, NULL, 1, NULL, 2, 1),

	(3, 'Nasim Al-Sahra', 'نسيم الصحراء', NULL, 'ARABIAN', 'MALE',
	    'WAITING_FOR_LABORATORY', 'UNKNOWN',
	    '33333333-3333-4333-8333-333333333333', NULL, NULL,
	    NULL, '985101000100003', 'Kuhailan',
	    '2025-03-18', NULL, '2025-06-20', '2025-04-02', NULL, false,
	    NULL, NULL, 'Awaiting DNA parentage verification.',
	    1, 2, 1, NULL, 1, NULL, 1, 1),

	(4, 'Bint Misr', 'بنت مصر', 'EG', 'ARABIAN', 'BROODMARE',
	    'REGISTER_IN_STUDBOOK', 'BEAUTY',
	    '44444444-4444-4444-8444-444444444444', '818002W00000044', 'AH-2001',
	    'EAO-7788', '985101000100004', 'Dahman',
	    '2019-05-22', '2023-03-01', '2023-02-10', NULL, '2023-01-15', true,
	    4, 12, 'Imported from Egypt in 2023.',
	    NULL, NULL, 2, 2, 1, 2, 3, 1);

INSERT INTO horse_owner (horse_id, owner_id) VALUES
	(1, 1),
	(2, 1),
	(2, 3),   -- co-owned, which is what the M:N table is for
	(3, 1),
	(4, 2);

INSERT INTO horse_breeder (horse_id, owner_id) VALUES
	(3, 1),   -- the dam's owner at foaling
	(4, 2);

-- ------------------------------------------------------------------ events
INSERT INTO event_type (id, type, description, selectable) VALUES
	(1, 'CHANGE_OWNER',  'Ownership Change',      true),
	(2, 'FOAL_ABORTION', 'Foal Abortion',         true),
	(3, 'NEW_FOAL',      'New Foal Registration', true),
	(4, 'DEATH',         'Death',                 true),
	(5, 'IMPORT',        'Import',                true),
	(6, 'EXPORT',        'Export',                true),
	(7, 'GELDING',       'Gelding',               true),
	(8, 'COVERED',       'Covered',               true);

INSERT INTO event (id, date, description, additional_information, cover, pregnant,
                   twins, horse_sex, type_id, horse_primary_id, horse_secondary_id,
                   horse_offspring_id, country_id) VALUES
	(1, '2023-01-15', 'Imported from Egypt', 'Permit IMP-2023-0042',
	    NULL, NULL, NULL, NULL, 5, 4, NULL, NULL, 2),
	(2, '2024-06-01', 'Covered by Sahm Al-Sahra', NULL,
	    true, true, false, NULL, 8, 2, 1, NULL, NULL),
	(3, '2025-03-18', 'Colt foal born', NULL,
	    NULL, NULL, false, 0, 3, 2, 1, 3, NULL),
	(4, '2026-02-09', 'Sold at private treaty', 'Contract 2026/118',
	    NULL, NULL, NULL, NULL, 1, 4, NULL, NULL, NULL);

-- the change of owner on horse 4: from Fatima to the Sahara Arabians company
INSERT INTO event_old_owner (event_id, owner_id) VALUES (4, 2);
INSERT INTO event_new_owner (event_id, owner_id) VALUES (4, 3);

-- ------------------------------------------------------------------- files
INSERT INTO file (id, file_type, file_name, file_path, file_size, mime_type,
                  document_type, is_avatar, horse_id) VALUES
	(1, 'DOCUMENT', 'passport_bint_misr.pdf', '/studlib/files/4/passport.pdf',
	    248123, 'application/pdf', 0, false, 4),
	(2, 'PHOTO', 'sahm.jpg', '/studlib/files/1/sahm.jpg',
	    91234, 'image/jpeg', 2, true, 1);

-- ------------------------------------------------------------ audit trail
-- Nothing fills these automatically -- there are no triggers in the sandbox.
-- The revision row comes first, because horse_aud.rev is an FK to it.
INSERT INTO revision_info (id, revision_timestamp, custom_timestamp, username,
                           usern_fullname, ip_address) VALUES
	(1, 1700000000000, '2023-11-14 22:13:20', 'vet@lsb.ly', 'Dr. Salem Ahmed', '10.0.0.5'),
	(2, 1770000000000, '2026-02-09 09:20:00', 'vet@lsb.ly', 'Dr. Salem Ahmed', '10.0.0.5');

INSERT INTO horse_aud (rev, revtype, id, name, local_name, breed, sex, status,
                       uuid, registry_id, date_of_birth, birthplace_country_id,
                       color_id) VALUES
	-- 0 = ADD: horse 4 first appears
	(1, 0, 4, 'Bint Misr', 'بنت مصر', 'ARABIAN', 'BROODMARE', 'NEW_IMPORTED',
	    '44444444-4444-4444-8444-444444444444', NULL, '2019-05-22', 2, 3),
	-- 1 = MOD: registered, and given its registry id
	(2, 1, 4, 'Bint Misr', 'بنت مصر', 'ARABIAN', 'BROODMARE', 'REGISTER_IN_STUDBOOK',
	    '44444444-4444-4444-8444-444444444444', 'AH-2001', '2019-05-22', 2, 3);

INSERT INTO event_aud (rev, revtype, id, date, description, type_id,
                       horse_primary_id) VALUES
	(2, 0, 4, '2026-02-09', 'Sold at private treaty', 1, 4);

INSERT INTO horse_owner_aud (rev, revtype, horse_id, owner_id) VALUES
	(1, 0, 4, 2),
	(2, 2, 4, 2);   -- 2 = DEL, the old owner comes off

-- the identity columns were fed explicit ids above, so bring the sequences up
SELECT setval('country_id_seq',          (SELECT max(id) FROM country));
SELECT setval('horse_color_id_seq',      (SELECT max(id) FROM horse_color));
SELECT setval('book_type_id_seq',        (SELECT max(id) FROM book_type));
SELECT setval('laboratory_id_seq',       (SELECT max(id) FROM laboratory));
SELECT setval('application_user_id_seq', (SELECT max(id) FROM application_user));
SELECT setval('owner_id_seq',            (SELECT max(id) FROM owner));
SELECT setval('horse_id_seq',            (SELECT max(id) FROM horse));
SELECT setval('event_type_id_seq',       (SELECT max(id) FROM event_type));
SELECT setval('event_id_seq',            (SELECT max(id) FROM event));
SELECT setval('file_id_seq',             (SELECT max(id) FROM file));
SELECT setval('revision_info_id_seq',    (SELECT max(id) FROM revision_info));

COMMIT;
