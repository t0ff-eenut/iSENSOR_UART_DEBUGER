#include "mlp_int8.h"

/* float → int8 양자화 (symmetric) */
static int8_t _to_q8(float v, float scale) {
    float q = v / scale;
    if (q >  127.0f) return  127;
    if (q < -127.0f) return -127;
    return (int8_t)(int32_t)(q >= 0.0f ? q + 0.5f : q - 0.5f);
}

/* int8 완전연결층: int32 MAC 누산 → float 출력 */
static void _fc_q8(
    const int8_t  *in,   int     in_n,
    const int8_t  *W_q,  float   in_scale,
    const int32_t *b_q,  float   acc_scale,
    float *out, int out_n, int relu
) {
    for (int i = 0; i < out_n; i++) {
        int32_t acc = b_q[i];
        const int8_t *wi = W_q + i * in_n;
        for (int j = 0; j < in_n; j++)
            acc += (int32_t)wi[j] * (int32_t)in[j];  /* int8×int8→int32 */
        float s = (float)acc * acc_scale;
        out[i] = (relu && s < 0.0f) ? 0.0f : s;
    }
}

int mlp_int8_infer(const float *raw_input, float *human_prob) {
    /* Step 1: StandardScaler 정규화 */
    float x[25];
    for (int i = 0; i < 25; i++)
        x[i] = (raw_input[i] - MLP_SCALER_MEAN[i]) / MLP_SCALER_STD[i];

    /* Step 2: 입력 → int8 양자화 */
    int8_t x_q[25];
    for (int i = 0; i < 25; i++) x_q[i] = _to_q8(x[i], MLP_L1_IN_SCALE);

    /* Step 3: Layer 1 */
    float h1[128];
    _fc_q8(x_q, 25, MLP_W1_Q, MLP_L1_IN_SCALE,
           MLP_B1_Q, MLP_L1_ACC_SCALE, h1, 128, 1);
    int8_t h1_q[128];
    for (int i = 0; i < 128; i++) h1_q[i] = _to_q8(h1[i], MLP_L2_IN_SCALE);

    /* Step 4: Layer 2 */
    float h2[64];
    _fc_q8(h1_q, 128, MLP_W2_Q, MLP_L2_IN_SCALE,
           MLP_B2_Q, MLP_L2_ACC_SCALE, h2, 64, 1);
    int8_t h2_q[64];
    for (int i = 0; i < 64; i++) h2_q[i] = _to_q8(h2[i], MLP_L3_IN_SCALE);

    /* Step 5: Layer 3 */
    float h3[32];
    _fc_q8(h2_q, 64, MLP_W3_Q, MLP_L3_IN_SCALE,
           MLP_B3_Q, MLP_L3_ACC_SCALE, h3, 32, 1);
    int8_t h3_q[32];
    for (int i = 0; i < 32; i++) h3_q[i] = _to_q8(h3[i], MLP_L4_IN_SCALE);

    /* Step 6: Layer 4 */
    float out[2];
    _fc_q8(h3_q, 32, MLP_W4_Q, MLP_L4_IN_SCALE,
           MLP_B4_Q, MLP_L4_ACC_SCALE, out, 2, 0);

    /* Step Final: Softmax → 확률 */
    float mx = out[0] > out[1] ? out[0] : out[1];
    float e0 = expf(out[0] - mx), e1 = expf(out[1] - mx);
    *human_prob = e1 / (e0 + e1);
    return e1 > e0 ? 1 : 0;
}
