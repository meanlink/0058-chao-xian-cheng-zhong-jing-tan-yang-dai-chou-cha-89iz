CREATE TABLE IF NOT EXISTS coast_samples(
 segment text REFERENCES coast_segments(code),
 bag int NOT NULL CHECK(bag>0),
 first_kg numeric(6,2) NOT NULL CHECK(first_kg>0),
 second_kg numeric(6,2) NOT NULL CHECK(second_kg>0),
 status text NOT NULL CHECK(status IN('awaiting','disputed','accepted')),
 PRIMARY KEY(segment,bag)
);
