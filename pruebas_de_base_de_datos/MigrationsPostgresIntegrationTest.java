package com.handwash.repository;

import com.handwash.model.*;
import com.handwash.service.ProtocolProfileService;
import com.handwash.service.SessionAuditService;
import com.handwash.strategy.BalancedFrictionStrategy;
import com.handwash.strategy.ProtocolProfileStrategy;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

/** Opt-in: applies V1-V8 with Flyway on a disposable local PostgreSQL and exercises V7/V8. */
@EnabledIfEnvironmentVariable(named = "HANDWASH_TEST_PG_URL", matches = "jdbc:postgresql://127\\.0\\.0\\.1:[0-9]+/handwash_test")
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class MigrationsPostgresIntegrationTest {
    private static final DriverManagerDataSource DS =
        new DriverManagerDataSource(System.getenv("HANDWASH_TEST_PG_URL"), "handwash_test", "");
    private final JdbcTemplate jdbc = new JdbcTemplate(DS);

    @Test @Order(1) void flywayAppliesAndValidatesAllSeventeenMigrations() {
        var flyway = Flyway.configure().dataSource(DS).locations("classpath:db/migration").load();
        var result = flyway.migrate();
        flyway.validate();
        assertEquals("17", flyway.info().current().getVersion().getVersion());
        assertEquals(17, jdbc.queryForObject("SELECT COUNT(*) FROM flyway_schema_history WHERE success", Integer.class));
    }

    @Test @Order(2) void protocolProfilesSeedAppendAuditAndConstraints() {
        var audit = new SessionAuditService(new SessionAuditRepository(jdbc));
        var service = new ProtocolProfileService(new ProtocolProfileRepository(jdbc), new com.handwash.repository.ChangeControlRepository(jdbc), audit, new DataSourceTransactionManager(DS));
        assertEquals(ProtocolProfile.PREDETERMINADO.tiemposPasoMs(), service.perfilVigente().tiemposPasoMs());
        assertEquals(1, service.perfilVigente().version());
        var v2 = service.crearVersion(ProtocolProfile.uniforme(8_000L), 70_000L, "admin-sub", "Ajuste de prueba en PostgreSQL").perfil();
        assertEquals(2, v2.version());
        assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM wash_audit_events WHERE event_type='PROTOCOL_PROFILE_VERSION_CREATED' AND reason_code='VERSION_2'", Integer.class));
        assertThrows(DuplicateKeyException.class, () -> new ProtocolProfileRepository(jdbc).insert(v2, "duplicado", null, "ACTIVE"));
        assertThrows(DataIntegrityViolationException.class, () -> jdbc.update(
            "INSERT INTO protocol_profiles VALUES (9, 2000, 7000, 7000, 7000, 7000, 7000, 60000, 'x', 0)"));

        String sessionId = UUID.randomUUID().toString();
