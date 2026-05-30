package com.soham.gateway.model;

import lombok.Data;

@Data
public class ChatResponse {
    private String responseText;
    private String modelUsed;
    private String taskType;
    private Integer latencyMs;
    private String requestId;
    private boolean cacheHit;
}
