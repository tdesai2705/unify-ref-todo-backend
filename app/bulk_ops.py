def execute_bulk_complete(todo_ids, db, Todo):  # bulk feature v2
    """Mark multiple todos completed. db and Todo passed in to avoid Flask imports."""
    updated = []
    for tid in todo_ids:
        todo = Todo.query.get(tid)
        if todo:
            todo.completed = True
            updated.append(tid)
    not_found = [tid for tid in todo_ids if tid not in updated]
    db.session.commit()
    return {
        'completed': updated,
        'count': len(updated),
        'skipped': not_found,
        'total_requested': len(todo_ids),
        'success_rate': round(len(updated) / len(todo_ids) * 100, 1) if todo_ids else 0,
        'processed': True,
        'not_found_count': len(not_found),
        'all_completed': len(not_found) == 0,
        'fully_completed': len(not_found) == 0 and len(updated) > 0,
    }


# smart-tests isolation probe: bulk_ops-only diff for PTS subsetting test
