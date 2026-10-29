package com.handwash.security;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.embedded.EmbeddedDatabase;
import org.springframework.jdbc.datasource.embedded.EmbeddedDatabaseBuilder;
import org.springframework.jdbc.datasource.embedded.EmbeddedDatabaseType;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.regex.Pattern;

import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * R-08 / R-09: the records about washes are anonymous and hold no media. If someone adds a column that could
 * identify the person who washed, or a binary column, this test fails and forces a conscious decision.
 */
class NoPersonalDataSchemaTest {
    private static final Set<String> WASH_TABLES = Set.of("WASH_ENCOUNTERS", "WASH_AUDIT_EVENTS", "FRICTION_ATTEMPT_VALIDATION",
        "FRICTION_STEP_VALIDATION", "FAILED_ATTEMPTS", "WASH_REPORT_EVIDENCE", "AUDIT_SEALS");
    private static final Pattern IDENTITY = Pattern.compile("(?i)(^|_)(name|email|mail|phone|telefono|document|cedula|dni|passport|"
        + "face|rostro|employee|empleado|patient|paciente|badge|nfc|rfid|username|user_id)(_|$)");
    /** Staff accounts (operators/admins) are referenced by their opaque Cognito subject, never by name. */
    private static final Set<String> ALLOWED = Set.of("ACTOR_SUBJECT");
    private EmbeddedDatabase database;
    private JdbcTemplate jdbc;

    @BeforeEach
    void setUp() {
        database = new EmbeddedDatabaseBuilder().setType(EmbeddedDatabaseType.H2).addScript("schema.sql").build();
        jdbc = new JdbcTemplate(database);
    }
