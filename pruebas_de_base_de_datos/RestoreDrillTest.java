package com.handwash.repository;

import com.handwash.model.SessionAuditEvent;
import com.handwash.service.audit.AuditChainHasher;
import com.handwash.service.audit.AuditChainVerifier;
import com.handwash.service.audit.AuditSealService;
import com.handwash.service.audit.UnavailableAuditSealStore;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Opt-in restore rehearsal driven by scripts/chaos/restore-drill.sh against disposable local PostgreSQL:
 * HANDWASH_DRILL=seed fills a database, the script dumps and restores it, HANDWASH_DRILL=verify proves the
 * restored copy has the same schema history, rows, audit chain and seal. Nothing here touches AWS.
 */
@EnabledIfEnvironmentVariable(named = "HANDWASH_DRILL", matches = "seed|verify")
@EnabledIfEnvironmentVariable(named = "HANDWASH_TEST_PG_URL", matches = "jdbc:postgresql://127\\.0\\.0\\.1:[0-9]+/[a-z_0-9]+")
class RestoreDrillTest {
    private static final int EVENTS = 500;
    private final DriverManagerDataSource ds =
        new DriverManagerDataSource(System.getenv("HANDWASH_TEST_PG_URL"), "handwash_test", "");
    private final JdbcTemplate jdbc = new JdbcTemplate(ds);
    private final AuditChainHasher hasher = new AuditChainHasher("drill-secret-" + "x".repeat(40));

    @Test
    void seedOrVerify() {
        if ("seed".equals(System.getenv("HANDWASH_DRILL"))) seed(); else verify();
    }

    private void seed() {
