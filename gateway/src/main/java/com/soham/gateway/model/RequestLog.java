package com.soham.gateway.model;

import jakarta.persistence.*;
import lombok.Data;
import java.time.Instant;

@Data
@Entity
@Table(name = "request_log")
public class RequestLog {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private String id;

    @Column(name = "request_id")
    private String requestId;

    @Column(columnDefinition = "TEXT")
    private String prompt;

    @Column(name = "task_type")
    private String taskType;

    @Column(name = "model_used")
    private String modelUsed;

    @Column(name = "response_text", columnDefinition = "TEXT")
    private String responseText;

    @Column(name = "latency_ms")
    private Integer latencyMs;

    @Column(name = "api_key_hash")
    private String apiKeyHash;

    @Column(name = "created_at")
    private Instant createdAt = Instant.now();
}
