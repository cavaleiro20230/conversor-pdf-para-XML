package com.analytics.model;

import lombok.Data;

@Data
public class UserStats {
    private int totalUsers;
    private int activeUsers;
    private int newSignups;
    private double userRetention;
    private double totalUsersGrowth;
    private double activeUsersGrowth;
    private double newSignupsGrowth;
    private double retentionGrowth;
}