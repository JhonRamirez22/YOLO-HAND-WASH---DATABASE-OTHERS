package com.handwash.repository;

import com.handwash.model.*;
import com.handwash.strategy.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import static org.junit.jupiter.api.Assertions.*;

/** Opt-in disposable local PostgreSQL only; migrates the schema itself (Flyway is idempotent). */
@EnabledIfEnvironmentVariable(named="HANDWASH_TEST_PG_URL",matches="jdbc:postgresql://127\\.0\\.0\\.1:[0-9]+/handwash_test")
class FrictionPostgresIntegrationTest {
    @Test void postgresWritesAreAtomicIdempotentAndTerminalResultsImmutable() {
        var ds=new DriverManagerDataSource(System.getenv("HANDWASH_TEST_PG_URL"),"handwash_test","");
        // Idempotent: class order is not guaranteed, so this test must not rely on another class migrating first.
