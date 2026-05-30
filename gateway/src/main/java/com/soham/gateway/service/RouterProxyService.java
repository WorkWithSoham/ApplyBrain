package com.soham.gateway.service;

import com.soham.gateway.model.ChatRequest;
import com.soham.gateway.model.ChatResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import org.springframework.http.*;

import java.util.HashMap;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class RouterProxyService {

    private final RestTemplate restTemplate;

    @Value("${gateway.router-url:http://router:8081}")
    private String routerUrl;

    public ChatResponse forward(ChatRequest request, String requestId) {
        String url = routerUrl + "/route";

        // Build the payload the Python router expects
        Map<String, Object> body = new HashMap<>();
        body.put("prompt", request.getPrompt());
        body.put("task_type", request.getTaskType());
        body.put("request_id", requestId);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(body, headers);

        try {
            ResponseEntity<ChatResponse> response = restTemplate.exchange(
                url, HttpMethod.POST, entity, ChatResponse.class
            );
            return response.getBody();
        } catch (Exception e) {
            log.error("Router call failed: {}", e.getMessage());
            ChatResponse errorResponse = new ChatResponse();
            errorResponse.setResponseText("Router unavailable: " + e.getMessage());
            errorResponse.setModelUsed("none");
            errorResponse.setTaskType(request.getTaskType());
            errorResponse.setRequestId(requestId);
            return errorResponse;
        }
    }
}
