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
        jdbc = new JdbcTemplate(ds);
        repo = new FrictionAttemptRepository(jdbc);
    }

    private static List<FrictionEvaluation.Step> steps(int validated) {
        return BalancedFrictionStrategy.STEPS.stream().map(step -> new FrictionEvaluation.Step(step.name(),
            step.getNumero() <= validated ? FrictionEvaluation.StepStatus.VALIDADO : FrictionEvaluation.StepStatus.PENDIENTE,
            step.getNumero() <= validated ? 7_000 : 0, 7_000, null)).toList();
    }

    private void finished(String session, WashOutcome outcome, String result, String reason,
                          int validated, long finishedAt, String evidence) {
