package com.handwash.repository;

import com.handwash.model.FrictionAttemptRecord;
import com.handwash.model.FrictionEvaluation;
import com.handwash.model.WashOutcome;
import com.handwash.strategy.BalancedFrictionStrategy;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class WashReportRepositoryTest {
    private final JdbcTemplate jdbc;
    private final FrictionAttemptRepository repo;

    WashReportRepositoryTest() {
        var ds = new DriverManagerDataSource("jdbc:h2:mem:" + java.util.UUID.randomUUID() + ";DB_CLOSE_DELAY=-1", "sa", "");
        new ResourceDatabasePopulator(new ClassPathResource("schema.sql")).execute(ds);
