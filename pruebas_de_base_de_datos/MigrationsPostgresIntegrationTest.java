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
