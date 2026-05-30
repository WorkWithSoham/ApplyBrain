package com.soham.gateway.filter;

import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.time.Duration;
import java.util.Arrays;
import java.util.List;

/**
 * Filter that runs on every request:
 *   1. Validates the X-API-Key header against a configured list
 *   2. Enforces a per-key rate limit using Redis (sliding window counter)
 *
 * Rate limit: 60 requests/minute per API key (configurable).
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class ApiKeyFilter implements Filter {

    private final StringRedisTemplate redis;

    @Value("${gateway.api-keys}")
    private String rawApiKeys;

    @Value("${gateway.rate-limit.requests-per-minute:60}")
    private int requestsPerMinute;

    @Override
    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain)
            throws IOException, ServletException {

        HttpServletRequest  request  = (HttpServletRequest) req;
        HttpServletResponse response = (HttpServletResponse) res;

        // Skip health checks
        if (request.getRequestURI().contains("/health") || request.getRequestURI().contains("/actuator")) {
            chain.doFilter(req, res);
            return;
        }

        String apiKey = request.getHeader("X-API-Key");
        List<String> validKeys = Arrays.asList(rawApiKeys.split(","));

        // 1. Auth check
        if (apiKey == null || !validKeys.contains(apiKey.trim())) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.getWriter().write("{\"error\": \"Invalid or missing API key\"}");
            return;
        }

        // 2. Rate limiting via Redis INCR + EXPIRE
        String rateLimitKey = "rl:" + apiKey + ":" + (System.currentTimeMillis() / 60_000);
        Long count = redis.opsForValue().increment(rateLimitKey);
        if (count != null && count == 1) {
            redis.expire(rateLimitKey, Duration.ofMinutes(2));
        }

        if (count != null && count > requestsPerMinute) {
            response.setStatus(429);
            response.setHeader("Retry-After", "60");
            response.getWriter().write("{\"error\": \"Rate limit exceeded\"}");
            log.warn("Rate limit hit for key: {}", apiKey.substring(0, 4) + "****");
            return;
        }

        chain.doFilter(req, res);
    }
}
