package com.soham.gateway.model;

import lombok.Data;

@Data
public class ChatRequest {
    private String prompt;
    private String taskType = "auto";
}
