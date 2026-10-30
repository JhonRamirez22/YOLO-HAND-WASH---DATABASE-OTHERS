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

