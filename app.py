import streamlit as st
import pandas as pd

from agent import (
    generate_sql,
    execute_sql,
    generate_answer,
    fix_sql,
    refresh_database
)

from data_manager import replace_database


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="AI Data Analyst",
    page_icon="📊",
    layout="wide"
)


# ============================================================
# HEADER
# ============================================================

st.title("📊 AI Data Analyst")

st.caption(
    "Ask natural-language questions about your data."
)


# ============================================================
# SESSION STATE
# ============================================================

if "messages" not in st.session_state:

    st.session_state.messages = []


# ============================================================
# DATASET UPLOAD
# ============================================================

st.subheader("📁 Load Dataset")

uploaded_file = st.file_uploader(
    "Choose a CSV file",
    type=["csv"]
)


if uploaded_file is not None:

    st.write(
        f"Selected: **{uploaded_file.name}**"
    )


    if st.button("🚀 Load Dataset"):

        try:

            with st.spinner(
                "Loading dataset..."
            ):

                refresh_database()

                result = replace_database(
                    uploaded_file
                )

                refresh_database()


            st.session_state.messages = []


            st.success(
                "Dataset loaded successfully!"
            )


            if isinstance(
                result,
                dict
            ):

                if "table_name" in result:

                    st.write(
                        f"**Table:** `{result['table_name']}`"
                    )

                if "rows" in result:

                    st.write(
                        f"**Rows:** {result['rows']:,}"
                    )

                if "columns" in result:

                    st.write(
                        f"**Columns:** {result['columns']}"
                    )


            st.rerun()


        except Exception as e:

            st.error(
                "Could not load dataset."
            )

            st.exception(e)


# ============================================================
# DIVIDER
# ============================================================

st.divider()


# ============================================================
# CHAT HISTORY
# ============================================================

for message in st.session_state.messages:

    with st.chat_message(
        message["role"]
    ):

        st.markdown(
            message["content"]
        )


        # ----------------------------------------------------
        # SQL
        # ----------------------------------------------------

        if (
            message["role"] == "assistant"
            and message.get("sql")
        ):

            with st.expander(
                "🔍 View generated SQL"
            ):

                st.code(
                    message["sql"],
                    language="sql"
                )


        # ----------------------------------------------------
        # RESULT TABLE
        # ----------------------------------------------------

        if (
            message["role"] == "assistant"
            and message.get("data") is not None
        ):

            data = message["data"]


            # Don't show useless table for:
            #
            # COUNT(*) → 144
            # SUM(Sales) → 2297200
            # AVG(...) → ...
            #

            if not (
                len(data) == 1
                and len(data.columns) == 1
            ):

                if not data.empty:

                    st.dataframe(
                        data,
                        use_container_width=True
                    )


# ============================================================
# CHAT INPUT
# ============================================================

question = st.chat_input(
    "Ask a question about your data..."
)


# ============================================================
# PROCESS QUESTION
# ============================================================

if question:

    # --------------------------------------------------------
    # USER MESSAGE
    # --------------------------------------------------------

    st.session_state.messages.append(
        {
            "role": "user",
            "content": question
        }
    )


    with st.chat_message(
        "user"
    ):

        st.markdown(
            question
        )


    # --------------------------------------------------------
    # ASSISTANT
    # --------------------------------------------------------

    with st.chat_message(
        "assistant"
    ):

        try:

            # ================================================
            # GENERATE SQL
            # ================================================

            with st.spinner(
                "Analyzing your data..."
            ):

                sql = generate_sql(
                    question,
                    st.session_state.messages[:-1]
                )


            # ================================================
            # EXECUTE SQL
            # ================================================

            try:

                columns, rows = execute_sql(
                    sql
                )


            except Exception as first_error:

                with st.spinner(
                    "Fixing the query..."
                ):

                    sql = fix_sql(
                        question,
                        sql,
                        str(first_error),
                        st.session_state.messages[:-1]
                    )


                columns, rows = execute_sql(
                    sql
                )


            # ================================================
            # DATAFRAME
            # ================================================

            result_data = pd.DataFrame(
                rows,
                columns=columns
            )


            # ================================================
            # NATURAL LANGUAGE ANSWER
            # ================================================

            answer = generate_answer(
                question,
                sql,
                columns,
                rows,
                st.session_state.messages[:-1]
            )


            # ================================================
            # ANSWER
            # ================================================

            st.markdown(
                answer
            )


            # ================================================
            # SQL BELOW ANSWER
            # ================================================

            with st.expander(
                "🔍 View generated SQL"
            ):

                st.code(
                    sql,
                    language="sql"
                )


            # ================================================
            # DATA TABLE
            # ================================================

            if not (
                len(result_data) == 1
                and len(result_data.columns) == 1
            ):

                if not result_data.empty:

                    st.dataframe(
                        result_data,
                        use_container_width=True
                    )


            # ================================================
            # SAVE RESPONSE
            # ================================================

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                    "sql": sql,
                    "data": result_data
                }
            )


        except Exception as e:

            st.error(
                "I couldn't answer that question."
            )


            with st.expander(
                "Technical details"
            ):

                st.exception(e)