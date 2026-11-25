CREATE TABLE IF NOT EXISTS coast_haul(
 round text PRIMARY KEY REFERENCES coast_rounds(code),
 estimated_kg numeric(8,2) NOT NULL CHECK(estimated_kg>0),
 issued_at timestamptz NOT NULL DEFAULT now(),
 pieces jsonb NOT NULL
);
