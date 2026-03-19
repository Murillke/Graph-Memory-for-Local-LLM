-- Code Graph Schema
-- Separate graph for tracking code evolution
-- Links to conversation graph via LLM-powered semantic correlation

-- Commit node: Represents a git commit
CREATE NODE TABLE IF NOT EXISTS Commit (
    hash STRING PRIMARY KEY,
    message STRING,
    author STRING,
    author_email STRING,
    timestamp TIMESTAMP,
    branch STRING,
    parent_hashes STRING[],
    created_at TIMESTAMP DEFAULT current_timestamp()
);

-- File node: Represents a file in the repository
CREATE NODE TABLE IF NOT EXISTS File (
    path STRING PRIMARY KEY,
    language STRING,
    extension STRING,
    last_modified TIMESTAMP,
    created_at TIMESTAMP DEFAULT current_timestamp()
);

-- Function node: Represents a function/method/class in code
CREATE NODE TABLE IF NOT EXISTS Function (
    id STRING PRIMARY KEY,
    name STRING,
    signature STRING,
    file_path STRING,
    start_line INT64,
    end_line INT64,
    language STRING,
    created_at TIMESTAMP DEFAULT current_timestamp()
);

-- Commit modified File
CREATE REL TABLE IF NOT EXISTS MODIFIED (
    FROM Commit TO File,
    lines_added INT64,
    lines_removed INT64,
    change_type STRING,
    old_path STRING,
    created_at TIMESTAMP DEFAULT current_timestamp()
);

-- Commit added Function
CREATE REL TABLE IF NOT EXISTS ADDED_FUNCTION (
    FROM Commit TO Function,
    created_at TIMESTAMP DEFAULT current_timestamp()
);

-- Commit removed Function
CREATE REL TABLE IF NOT EXISTS REMOVED_FUNCTION (
    FROM Commit TO Function,
    created_at TIMESTAMP DEFAULT current_timestamp()
);

-- Commit modified Function
CREATE REL TABLE IF NOT EXISTS MODIFIED_FUNCTION (
    FROM Commit TO Function,
    lines_changed INT64,
    created_at TIMESTAMP DEFAULT current_timestamp()
);

-- File contains Function
CREATE REL TABLE IF NOT EXISTS CONTAINS (
    FROM File TO Function,
    created_at TIMESTAMP DEFAULT current_timestamp()
);

CREATE REL TABLE IF NOT EXISTS HAS_PARENT (
    FROM Commit TO Commit,
    created_at TIMESTAMP DEFAULT current_timestamp()
);

