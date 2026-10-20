package com.handwash.repository;

import com.handwash.model.*;
import com.handwash.strategy.*;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;
import org.springframework.core.io.ClassPathResource;
import static org.junit.jupiter.api.Assertions.*;

class FrictionAttemptRepositoryTest {
    @Test void idempotentAtomicPersistenceAndRestartInterruption() {
        var ds = new DriverManagerDataSource("jdbc:h2:mem:" + java.util.UUID.randomUUID() + ";DB_CLOSE_DELAY=-1", "sa", "");
        new ResourceDatabasePopulator(new ClassPathResource("schema.sql")).execute(ds);
        var jdbc = new JdbcTemplate(ds);
        var repo = new FrictionAttemptRepository(jdbc);
        var a = new BalancedFrictionAttempt("test", new BalancedFrictionStrategy(new DomesticStrategy()),1500,650);
        a.observe(WashStep.PASO_1_PALMAS,1000,0);
        var record = a.pendingRecord();
        repo.save(record);
        repo.save(record);
        assertEquals(1, jdbc.queryForObject("SELECT COUNT(*) FROM friction_attempt_validation", Integer.class));
        assertEquals(6, jdbc.queryForObject("SELECT COUNT(*) FROM friction_step_validation", Integer.class));
        assertEquals(1, repo.interruptAfterRestart());
        assertEquals(0, repo.interruptAfterRestart());
        assertEquals("BACKEND_RESTART", jdbc.queryForObject("SELECT reason FROM friction_attempt_validation", String.class));
        assertThrows(IllegalStateException.class, () -> repo.save(new FrictionAttemptRecord("test",1,record.policyVersion(),100,"ACTIVO",null,null,false,record.steps())));
    }
    @Test void failingStepWriteRollsBackEntireDecision() {
        var ds = new DriverManagerDataSource("jdbc:h2:mem:" + java.util.UUID.randomUUID() + ";DB_CLOSE_DELAY=-1", "sa", "");
        new ResourceDatabasePopulator(new ClassPathResource("schema.sql")).execute(ds);
        var jdbc = new JdbcTemplate(ds);
        var repo = new FrictionAttemptRepository(jdbc);
        var invalid = new FrictionEvaluation.Step("PASO_1_PALMAS", FrictionEvaluation.StepStatus.EN_CURSO, -1,6000,null);
        var record = new FrictionAttemptRecord("test",1,BalancedFrictionStrategy.VERSION,1,"ACTIVO",null,null,false,java.util.List.of(invalid));
