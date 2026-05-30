package com.soham.gateway.service;

import com.soham.gateway.model.ChatRequest;
import com.soham.gateway.model.ChatResponse;
import com.soham.gateway.model.RequestLog;
import com.soham.gateway.model.RequestLogRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;

@Slf4j
@Service
@RequiredArgsConstructor
public class AuditLogService {

    private final RequestLogRepository repository;

    @Async
    public void record(String requestId, ChatRequest request, ChatResponse response,
                       long latencyMs, String apiKey) {
        try {
            RequestLog log = new RequestLog();
            log.setRequestId(requestId);
            log.setPrompt(request.getPrompt());
            log.setTaskType(response.getTaskType());
            log.setModelUsed(response.getModelUsed());
            log.setResponseText(response.getResponseText());
            log.setLatencyMs((int) latencyMs);
            log.setApiKeyHash(sha256(apiKey));
            repository.save(log);
        } catch (Exception e) {
            log.error("Failed to write audit log: {}", e.getMessage());
        }
    }

    private String sha256(String input) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(input.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(hash);
        } catch (Exception e) {
            return "hash-error";
        }
    }
}
