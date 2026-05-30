package com.soham.gateway.controller;

import com.soham.gateway.model.ChatRequest;
import com.soham.gateway.model.ChatResponse;
import com.soham.gateway.service.AuditLogService;
import com.soham.gateway.service.RouterProxyService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;

@Slf4j
@RestController
@RequestMapping("/v1")
@RequiredArgsConstructor
public class GatewayController {

    private final RouterProxyService routerProxy;
    private final AuditLogService auditLog;

    /**
     * Main chat endpoint. The gateway:
     * 1. Validates the API key (handled by ApiKeyFilter)
     * 2. Logs the incoming request
     * 3. Forwards to the Python router service
     * 4. Logs the response + latency
     * 5. Returns the result to the client
     */
    @PostMapping("/chat")
    public ResponseEntity<ChatResponse> chat(
            @RequestBody ChatRequest request,
            @RequestHeader("X-API-Key") String apiKey,
            @RequestHeader(value = "X-Request-Id", required = false) String requestId
    ) {
        long start = Instant.now().toEpochMilli();
        log.info("Incoming request: requestId={} taskType={}", requestId, request.getTaskType());

        // Forward to router — it decides which model to call
        ChatResponse response = routerProxy.forward(request, requestId);

        long latencyMs = Instant.now().toEpochMilli() - start;
        auditLog.record(requestId, request, response, latencyMs, apiKey);

        log.info("Completed: requestId={} model={} latencyMs={}", requestId, response.getModelUsed(), latencyMs);
        return ResponseEntity.ok(response);
    }

    @GetMapping("/health")
    public ResponseEntity<String> health() {
        return ResponseEntity.ok("OK");
    }
}
