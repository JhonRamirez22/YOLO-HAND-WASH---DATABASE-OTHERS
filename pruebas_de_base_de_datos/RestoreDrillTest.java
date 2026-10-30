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
