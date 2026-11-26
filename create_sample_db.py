"""Creates a sample secondary company database (company_hr.db) for testing joins & ML analysis."""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "company_hr.db")


def create_sample_db() -> str:
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE hr_employees (
            employee_id TEXT PRIMARY KEY,
            department TEXT NOT NULL,
            role TEXT NOT NULL,
            location TEXT NOT NULL,
            manager_name TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE project_allocations (
            employee_id TEXT PRIMARY KEY,
            project_name TEXT NOT NULL,
            required_skill TEXT NOT NULL,
            target_quarter TEXT NOT NULL,
            revenue_impact_usd INTEGER NOT NULL
        )
        """
    )

    employees = [
        ("EMP001", "Cloud Infrastructure", "Cloud Engineer", "Bengaluru", "Karthik Rao"),
        ("EMP002", "Data Engineering", "SQL Developer", "Chennai", "Meenakshi S"),
        ("EMP003", "Cloud Infrastructure", "Azure Specialist", "Hyderabad", "Karthik Rao"),
        ("EMP004", "Backend Engineering", "Junior Developer", "Pune", "Rohan Das"),
        ("EMP005", "Cloud Infrastructure", "Solutions Architect", "Bengaluru", "Karthik Rao"),
        ("EMP006", "Cloud Infrastructure", "Systems Admin", "Mumbai", "Karthik Rao"),
        ("EMP007", "Data Engineering", "Associate Engineer", "Chennai", "Meenakshi S"),
        ("EMP008", "Data Engineering", "Database Admin", "Hyderabad", "Meenakshi S"),
        ("EMP009", "Cloud Infrastructure", "AWS Developer", "Bengaluru", "Karthik Rao"),
        ("EMP010", "Network Operations", "Network Analyst", "Pune", "Arvind Nair"),
        ("EMP011", "CRM & Enterprise", "Salesforce Admin", "Chennai", "Divya Menon"),
        ("EMP012", "Data Science", "Data Analyst", "Bengaluru", "Meenakshi S"),
        ("EMP013", "CRM & Enterprise", "SAP Consultant", "Mumbai", "Divya Menon"),
        ("EMP014", "Platform Engineering", "DevOps Engineer", "Hyderabad", "Rohan Das"),
        ("EMP015", "Frontend Engineering", "UI Developer", "Pune", "Rohan Das"),
        ("EMP016", "Cloud Infrastructure", "Cloud Associate", "Bengaluru", "Karthik Rao"),
        ("EMP017", "Data Science", "ML Engineer", "Chennai", "Meenakshi S"),
        ("EMP018", "Platform Engineering", "SRE", "Hyderabad", "Rohan Das"),
        ("EMP019", "Cloud Infrastructure", "Support Engineer", "Pune", "Karthik Rao"),
        ("EMP020", "Frontend Engineering", "Senior UI Dev", "Bengaluru", "Rohan Das"),
        ("EMP021", "Cloud Infrastructure", "Architect", "Mumbai", "Karthik Rao"),
        ("EMP022", "Data Engineering", "Junior Analyst", "Chennai", "Meenakshi S"),
        ("EMP023", "Cloud Infrastructure", "Cloud Engineer", "Hyderabad", "Karthik Rao"),
        ("EMP024", "Network Operations", "Network Tech", "Pune", "Arvind Nair"),
    ]

    projects = [
        ("EMP001", "Cloud Migration Phase 2", "AWS Cloud Practitioner", "Q4-2026", 120000),
        ("EMP002", "FinTech Data Warehouse", "Oracle SQL Database", "Q4-2026", 95000),
        ("EMP003", "Enterprise Azure Rollout", "Azure Fundamentals", "Q4-2026", 110000),
        ("EMP004", "Core API Modernization", "Python Programming", "Q1-2027", 80000),
        ("EMP005", "Cloud Migration Phase 2", "AWS Solutions Architect", "Q4-2026", 180000),
        ("EMP006", "Enterprise Azure Rollout", "Microsoft Azure Admin", "Q1-2027", 90000),
        ("EMP007", "GCP Analytics Hub", "Google Cloud Associate", "Q1-2027", 75000),
        ("EMP008", "FinTech Data Warehouse", "Oracle Database Admin", "Q4-2026", 140000),
        ("EMP009", "Serverless Billing", "AWS Certified Developer", "Q4-2026", 130000),
        ("EMP010", "Zero-Trust Campus Net", "Cisco CCNA Networking", "Q1-2027", 70000),
        ("EMP011", "Global CRM Upgrade", "Salesforce Administrator", "Q4-2026", 105000),
        ("EMP012", "Churn Prediction Suite", "Python Data Science", "Q4-2026", 115000),
        ("EMP013", "ERP Finance Sync", "SAP Basics", "Q4-2026", 85000),
        ("EMP014", "K8s Platform Consolidation", "Docker & Kubernetes", "Q4-2026", 160000),
        ("EMP015", "Customer Portal v3", "React Frontend Dev", "Q4-2026", 95000),
        ("EMP016", "Cloud Migration Phase 2", "AWS Cloud Practitioner", "Q4-2026", 90000),
        ("EMP017", "Churn Prediction Suite", "Python Data Science", "Q1-2027", 125000),
        ("EMP018", "K8s Platform Consolidation", "Docker & Kubernetes", "Q1-2027", 135000),
        ("EMP019", "Enterprise Azure Rollout", "Azure Fundamentals", "Q4-2026", 80000),
        ("EMP020", "Customer Portal v3", "React Frontend Dev", "Q1-2027", 110000),
        ("EMP021", "Cloud Migration Phase 2", "AWS Solutions Architect", "Q4-2026", 175000),
        ("EMP022", "FinTech Data Warehouse", "Oracle SQL Database", "Q1-2027", 70000),
        ("EMP023", "GCP Analytics Hub", "Google Cloud Associate", "Q1-2027", 105000),
        ("EMP024", "Zero-Trust Campus Net", "Cisco CCNA Networking", "Q4-2026", 65000),
    ]

    cur.executemany("INSERT INTO hr_employees VALUES (?, ?, ?, ?, ?)", employees)
    cur.executemany("INSERT INTO project_allocations VALUES (?, ?, ?, ?, ?)", projects)
    conn.commit()
    conn.close()
    return DB_PATH


if __name__ == "__main__":
    path = create_sample_db()
    print(f"Created sample company DB: {path}")
