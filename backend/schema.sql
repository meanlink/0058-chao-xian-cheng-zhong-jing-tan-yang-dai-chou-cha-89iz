CREATE TABLE IF NOT EXISTS coast_rounds(
 code text PRIMARY KEY, shore text NOT NULL,
 status text NOT NULL DEFAULT 'open' CHECK (status IN('open','locked','issued'))
);
CREATE TABLE IF NOT EXISTS coast_segments(
 code text PRIMARY KEY, round text NOT NULL REFERENCES coast_rounds(code),
 name text NOT NULL, bags int NOT NULL CHECK(bags BETWEEN 1 AND 4000),
 UNIQUE(round,name)
);
