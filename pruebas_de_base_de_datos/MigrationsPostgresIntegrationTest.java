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
