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
        repo.save(new FrictionAttemptRecord(session, 1, BalancedFrictionStrategy.VERSION, 1, "ACTIVO",
            null, null, false, steps(0), finishedAt - 40_000, null, null, false, null, null));
        repo.save(new FrictionAttemptRecord(session, 1, BalancedFrictionStrategy.VERSION, 2, "INTERRUMPIDO",
            result, reason, true, steps(validated), finishedAt - 40_000, finishedAt, 40_000L,
            false, outcome, evidence));
    }

    @Test
    void listsFinishedWashesByDateAndOutcomeWithStepsAndPhotoStatus() {
        finished("good", WashOutcome.CORRECTO, "FRICTION_SEQUENCE_COMPLETE", null, 6, 2_000_000, null);
        finished("left", WashOutcome.REPORTADO, "INTERRUPTED", "HANDS_ABSENT", 2, 3_000_000, "DESACTIVADA");
        finished("old", WashOutcome.REPORTADO, "INTERRUPTED", "HANDS_ABSENT", 1, 500_000, "DESACTIVADA");

        var reported = repo.findReports(1_000_000, 4_000_000, WashOutcome.REPORTADO, 10);
        assertEquals(1, reported.size());
        var left = reported.get(0);
        assertEquals("left", left.sessionId());
        assertEquals(2_960_000L, left.inicioEpochMs());
        assertEquals(3_000_000L, left.finEpochMs());
        assertEquals(40_000L, left.duracionMs());
        assertEquals("DESACTIVADA", left.estadoEvidencia());
        assertEquals(2, left.pasos().stream().filter(s -> s.estado() == FrictionEvaluation.StepStatus.VALIDADO).count());

        var all = repo.findReports(1_000_000, 4_000_000, null, 10);
