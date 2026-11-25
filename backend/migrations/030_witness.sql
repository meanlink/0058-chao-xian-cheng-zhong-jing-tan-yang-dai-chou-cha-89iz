CREATE TABLE IF NOT EXISTS coast_witness(
 segment text NOT NULL, bag int NOT NULL,
 accepted_kg numeric(6,2) NOT NULL CHECK(accepted_kg>0),
 source text NOT NULL CHECK(source IN('first','second')),
 witness text NOT NULL, note text NOT NULL,
 PRIMARY KEY(segment,bag),
 FOREIGN KEY(segment,bag) REFERENCES coast_samples(segment,bag)
);
