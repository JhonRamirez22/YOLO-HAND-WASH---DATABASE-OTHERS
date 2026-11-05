package com.handwash.repository;

import com.handwash.model.StationRecord;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.embedded.EmbeddedDatabase;
import org.springframework.jdbc.datasource.embedded.EmbeddedDatabaseBuilder;
import org.springframework.jdbc.datasource.embedded.EmbeddedDatabaseType;

import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertNotNull;

class StationRepositoryTest {
    private EmbeddedDatabase database;
    private StationRepository repository;

    @BeforeEach
    void setUp() {
        database = new EmbeddedDatabaseBuilder().setType(EmbeddedDatabaseType.H2)
            .addScript("schema.sql").build();
        repository = new StationRepository(new JdbcTemplate(database));
    }

    @AfterEach
    void tearDown() {
        database.shutdown();
    }

    @Test
    void enrollmentCodeIsConsumedOnceAndExpiresStrictly() {
        repository.createEnrollmentCode("a".repeat(64), "Lavamanos 1", "admin", 100, 200);
        assertNotNull(repository.consumeEnrollmentCode("a".repeat(64), 150));
        assertNull(repository.consumeEnrollmentCode("a".repeat(64), 150));

        repository.createEnrollmentCode("b".repeat(64), "Lavamanos 2", "admin", 100, 200);
