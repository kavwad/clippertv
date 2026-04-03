-- Rename card_number → account_number in clipper_cards
-- Add card_serial column for physical card serial numbers
--
-- card_number stored short card serials (e.g. "1202425091") but
-- trips.account_number stores long account numbers (e.g. "100005510894").
-- These didn't match, making the join impossible.
-- After this migration, clipper_cards.account_number matches trips.account_number.

ALTER TABLE clipper_cards RENAME COLUMN card_number TO account_number;
ALTER TABLE clipper_cards ADD COLUMN card_serial TEXT;
