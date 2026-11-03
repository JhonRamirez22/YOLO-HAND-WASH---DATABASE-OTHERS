package com.handwash.repository;

import com.handwash.model.EncounterAuditRecord;
import com.handwash.model.SessionAuditEvent;
import com.handwash.service.SessionAuditService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.embedded.EmbeddedDatabase;
import org.springframework.jdbc.datasource.embedded.EmbeddedDatabaseBuilder;
import org.springframework.jdbc.datasource.embedded.EmbeddedDatabaseType;

import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class SessionAuditRepositoryTest {
    private EmbeddedDatabase database;
    private SessionAuditRepository repository;

    @BeforeEach
    void setUp() {
        database = new EmbeddedDatabaseBuilder().setType(EmbeddedDatabaseType.H2)
            .addScript("schema.sql").build();
        repository = new SessionAuditRepository(new JdbcTemplate(database));
    }

    @AfterEach
    void tearDown() {
        database.shutdown();
    }

    @Test
    void persistsMetadataAndPaginatesAuditEventsWithoutMediaFields() {
        String sessionId = UUID.randomUUID().toString();
        repository.createEncounter(new EncounterAuditRecord(sessionId, "DOMESTICO", "ACTIVE",
            1_000, null, "model-v1", "a".repeat(64), "dataset-v1", 0));
        repository.appendEvent(new SessionAuditEvent(0, sessionId, "STEP_CONFIRMED", "SYSTEM",
