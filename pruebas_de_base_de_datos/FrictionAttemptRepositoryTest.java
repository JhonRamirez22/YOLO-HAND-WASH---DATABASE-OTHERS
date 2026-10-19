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
